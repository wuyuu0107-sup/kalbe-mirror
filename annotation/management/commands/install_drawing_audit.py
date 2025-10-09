from django.core.management.base import BaseCommand
from django.db import connection

SQL = r"""
-- History table for drawing annotations
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

-- Trigger function to capture changes on annotation_annotation
-- NOTE: relies on public.jsonb_diff() that was installed by the JSON edits audit.
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
    values (NEW.id, NEW.document_id, NEW.patient_id, 'insert', NEW.drawing_data);
    return NEW;

  elsif tg_op = 'UPDATE' then
    d := public.jsonb_diff(OLD.drawing_data, NEW.drawing_data);
    insert into public.annotation_annotation_history(
      annotation_id, document_id, patient_id, op, old_data, new_data, diff
    )
    values (NEW.id, NEW.document_id, NEW.patient_id, 'update', OLD.drawing_data, NEW.drawing_data, d);
    return NEW;

  elsif tg_op = 'DELETE' then
    insert into public.annotation_annotation_history(
      annotation_id, document_id, patient_id, op, old_data
    )
    values (OLD.id, OLD.document_id, OLD.patient_id, 'delete', OLD.drawing_data);
    return OLD;
  end if;
end;
$$;

drop trigger if exists trg_audit_annotation_annotation on public.annotation_annotation;
create trigger trg_audit_annotation_annotation
after insert or update or delete on public.annotation_annotation
for each row execute function public.audit_annotation_annotation();
"""

class Command(BaseCommand):
    help = "Install drawing audit history (trigger + table). Assumes jsonb_diff() already exists."

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            cur.execute(SQL)
        self.stdout.write(self.style.SUCCESS("Installed drawing audit trigger & history table."))
