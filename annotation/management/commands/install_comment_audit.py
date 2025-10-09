# annotation/management/commands/install_comment_audit.py
from django.core.management.base import BaseCommand
from django.db import connection

SQL = r"""
-- History table for comments
create table if not exists public.annotation_comment_history (
  id            bigserial primary key,
  comment_id    bigint not null,
  document_id   bigint not null,
  patient_id    bigint,
  op            text not null check (op in ('insert','update','delete')),
  changed_at    timestamptz not null default now(),
  old_author    text,
  new_author    text,
  old_body      text,
  new_body      text
);

-- Trigger fn: capture old/new body & author on insert/update/delete
create or replace function public.audit_annotation_comment()
returns trigger
language plpgsql
security definer
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.annotation_comment_history(
      comment_id, document_id, patient_id, op,
      new_author, new_body
    )
    values (NEW.id, NEW.document_id, NEW.patient_id, 'insert',
            NEW.author, NEW.body);
    return NEW;

  elsif tg_op = 'UPDATE' then
    insert into public.annotation_comment_history(
      comment_id, document_id, patient_id, op,
      old_author, new_author, old_body, new_body
    )
    values (NEW.id, NEW.document_id, NEW.patient_id, 'update',
            OLD.author, NEW.author, OLD.body, NEW.body);
    return NEW;

  elsif tg_op = 'DELETE' then
    insert into public.annotation_comment_history(
      comment_id, document_id, patient_id, op,
      old_author, old_body
    )
    values (OLD.id, OLD.document_id, OLD.patient_id, 'delete',
            OLD.author, OLD.body);
    return OLD;
  end if;
end;
$$;

drop trigger if exists trg_audit_annotation_comment on public.annotation_comment;
create trigger trg_audit_annotation_comment
after insert or update or delete on public.annotation_comment
for each row execute function public.audit_annotation_comment();
"""

class Command(BaseCommand):
    help = "Install audit history trigger for annotation_comment."

    def handle(self, *args, **options):
        with connection.cursor() as cur:
            cur.execute(SQL)
        self.stdout.write(self.style.SUCCESS("Installed comment audit trigger & history table."))
