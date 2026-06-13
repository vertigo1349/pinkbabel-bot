create table if not exists public.pinkbabel_chats (
    chat_id bigint primary key,
    target_language text,
    auto_translate boolean not null default false
);

create table if not exists public.pinkbabel_users (
    chat_id bigint not null
        references public.pinkbabel_chats(chat_id) on delete cascade,
    user_id bigint not null,
    language text not null,
    primary key (chat_id, user_id)
);

alter table public.pinkbabel_chats enable row level security;
alter table public.pinkbabel_users enable row level security;

revoke all on table public.pinkbabel_chats from anon, authenticated;
revoke all on table public.pinkbabel_users from anon, authenticated;

grant all on table public.pinkbabel_chats to service_role;
grant all on table public.pinkbabel_users to service_role;
