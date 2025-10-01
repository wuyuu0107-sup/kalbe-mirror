from django.core.management.base import BaseCommand
from django.db import connection

SQL = r"""
-- 1) flatten JSON to path → value  (PL/pgSQL recursive, no CTE)
drop function if exists public.jsonb_each_recursive(jsonb);

create or replace function public.jsonb_each_recursive(data jsonb)
returns table(path text, value jsonb)
language plpgsql
immutable
as $$
declare
    k   text;
    i   int;
    v   jsonb;
    sub record;
begin
    if data is null then
        return;
    end if;

    if jsonb_typeof(data) = 'object' then
        for k in select jsonb_object_keys(data) loop
            v := data -> k;
            if jsonb_typeof(v) in ('object','array') then
                for sub in select * from public.jsonb_each_recursive(v) loop
                    path := case when sub.path = '' then k else k || '.' || sub.path end;
                    value := sub.value;
                    return next;
                end loop;
            else
                path := k;
                value := v;
                return next;
            end if;
        end loop;

    elsif jsonb_typeof(data) = 'array' then
        for i in 0..(jsonb_array_length(data)-1) loop
            v := data -> i;
            if jsonb_typeof(v) in ('object','array') then
                for sub in select * from public.jsonb_each_recursive(v) loop
                    path := '['||i||']' || case when sub.path = '' then '' else '.' || sub.path end;
                    value := sub.value;
                    return next;
                end loop;
            else
                path := '['||i||']';
                value := v;
                return next;
            end if;
        end loop;

    else
        -- scalar
        path := '';
        value := data;
        return next;
    end if;
end;
$$;

-- 2) diff old vs new → {added, removed, modified}
create or replace function public.jsonb_diff(old jsonb, new jsonb)
returns jsonb
language sql
immutable
as $$
with
o as (select * from public.jsonb_each_recursive(coalesce(old, '{}'::jsonb))),
n as (select * from public.jsonb_each_recursive(coalesce(new, '{}'::jsonb))),
paths as (select path from o union select path from n),

added as (
  select p.path, n.value as new
  from paths p
  left join o on o.path = p.path
  left join n on n.path = p.path
  where o.path is null and n.path is not null
),
removed as (
  select p.path, o.value as old
  from paths p
  left join o on o.path = p.path
  left join n on n.path = p.path
  where n.path is null and o.path is not null
),
modified as (
  select p.path, o.value as old, n.value as new
  from paths p
  join o on o.path = p.path
  join n on n.path = p.path
  where o.value is distinct from n.value
)
select jsonb_build_object(
  'added',    coalesce((select jsonb_agg(jsonb_build_object('path', path, 'new', new)) from added), '[]'::jsonb),
  'removed',  coalesce((select jsonb_agg(jsonb_build_object('path', path, 'old', old)) from removed), '[]'::jsonb),
  'modified', coalesce((select jsonb_agg(jsonb_build_object('path', path, 'old', old, 'new', new)) from modified), '[]'::jsonb)
);
$$;

-- 3) history table + trigger for annotation_document
create table if not exists public.annotation_document_history (
  id               bigserial primary key,
  document_id      bigint not null,
  op               text not null check (op in ('insert','update','delete')),
  changed_at       timestamptz not null default now(),
  old_payload      jsonb,
  new_payload      jsonb,
  diff             jsonb,
  storage_pdf_url  text,
  storage_json_url text
);

create or replace function public.audit_annotation_document()
returns trigger
language plpgsql
security definer
as $$
declare d jsonb;
begin
  if tg_op = 'INSERT' then
    insert into public.annotation_document_history(
      document_id, op, new_payload, diff,
      storage_pdf_url, storage_json_url
    )
    values (
      new.id, 'insert', new.payload_json, null,
      coalesce(new.meta->>'storage_pdf_url', null),
      coalesce(new.meta->>'storage_json_url', null)
    );
    return new;

  elsif tg_op = 'UPDATE' then
    d := public.jsonb_diff(old.payload_json, new.payload_json);
    insert into public.annotation_document_history(
      document_id, op, old_payload, new_payload, diff,
      storage_pdf_url, storage_json_url
    )
    values (
      new.id, 'update', old.payload_json, new.payload_json, d,
      coalesce(new.meta->>'storage_pdf_url', null),
      coalesce(new.meta->>'storage_json_url', null)
    );
    return new;

  elsif tg_op = 'DELETE' then
    insert into public.annotation_document_history(
      document_id, op, old_payload, diff
    )
    values (old.id, 'delete', old.payload_json, null);
    return old;
  end if;
end;
$$;

drop trigger if exists trg_audit_annotation_document on public.annotation_document;
create trigger trg_audit_annotation_document
after insert or update or delete on public.annotation_document
for each row execute function public.audit_annotation_document();

-- 4) OPTIONAL: history + trigger for annotation_annotation (drawings)
create table if not exists public.annotation_annotation_history (
  id            bigserial primary key,
  annotation_id bigint not null,
  document_id   bigint not null,
  patient_id    bigint not null,
  op            text not null check (op in ('insert','update','delete')),
  changed_at    timestamptz not null default now(),
  old_data      jsonb,
  new_data      jsonb,
  diff          jsonb
);

create or replace function public.audit_annotation_annotation()
returns trigger
language plpgsql
security definer
as $$
declare d jsonb;
begin
  if tg_op = 'INSERT' then
    insert into public.annotation_annotation_history(
      annotation_id, document_id, patient_id, op, new_data
    )
    values (new.id, new.document_id, new.patient_id, 'insert', new.drawing_data);
    return new;

  elsif tg_op = 'UPDATE' then
    d := public.jsonb_diff(old.drawing_data, new.drawing_data);
    insert into public.annotation_annotation_history(
      annotation_id, document_id, patient_id, op, old_data, new_data, diff
    )
    values (new.id, new.document_id, new.patient_id, 'update', old.drawing_data, new.drawing_data, d);
    return new;

  elsif tg_op = 'DELETE' then
    insert into public.annotation_annotation_history(
      annotation_id, document_id, patient_id, op, old_data
    )
    values (old.id, old.document_id, old.patient_id, 'delete', old.drawing_data);
    return old;
  end if;
end;
$$;

drop trigger if exists trg_audit_annotation_annotation on public.annotation_annotation;
create trigger trg_audit_annotation_annotation
after insert or update or delete on public.annotation_annotation
for each row execute function public.audit_annotation_annotation();
"""

class Command(BaseCommand):
    help = "Install JSON diff helpers and audit triggers into the connected database."

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            cur.execute(SQL)
        self.stdout.write(self.style.SUCCESS("Installed JSON audit functions & triggers."))
