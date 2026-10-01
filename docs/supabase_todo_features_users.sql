-- Supabase schema draft for scoped app users used by the ToDoFeatures plan.
-- Intended for future integration with Supabase Auth + Resend + Flask-side authorization.

create extension if not exists citext;

create table if not exists public.app_user_profiles (
    id bigserial primary key,
    auth_user_id uuid unique,
    email citext not null unique,
    group_id integer not null check (group_id between 1 and 5),
    group_code text not null check (group_code in ('admin', 'internal', 'hot', 'contractor', 'pais')),
    allowed_pages jsonb not null default '[]'::jsonb,
    landing_page text not null default '/home',
    scope_type text not null default 'none' check (scope_type in ('none', 'project_manager')),
    scope_value text not null default '',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint app_user_profiles_allowed_pages_is_array check (jsonb_typeof(allowed_pages) = 'array')
);

create index if not exists idx_app_user_profiles_group_code
    on public.app_user_profiles (group_code);

create index if not exists idx_app_user_profiles_active
    on public.app_user_profiles (active);

create index if not exists idx_app_user_profiles_scope
    on public.app_user_profiles (scope_type, scope_value);

create or replace function public.set_app_user_profiles_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_app_user_profiles_updated_at on public.app_user_profiles;

create trigger trg_app_user_profiles_updated_at
before update on public.app_user_profiles
for each row
execute function public.set_app_user_profiles_updated_at();

insert into public.app_user_profiles (
    email,
    group_id,
    group_code,
    allowed_pages,
    landing_page,
    scope_type,
    scope_value,
    active
)
values (
    'mayan.cohen@hot.net.il',
    3,
    'hot',
    '["features_status"]'::jsonb,
    '/features-status',
    'project_manager',
    'מעין כהן',
    true
)
on conflict (email) do update
set
    group_id = excluded.group_id,
    group_code = excluded.group_code,
    allowed_pages = excluded.allowed_pages,
    landing_page = excluded.landing_page,
    scope_type = excluded.scope_type,
    scope_value = excluded.scope_value,
    active = excluded.active,
    updated_at = now();
