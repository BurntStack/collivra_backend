-- 1. Add company_name to profiles for brands
alter table public.profiles add column if not exists company_name text;

-- Update trigger function to record company_name from user metadata
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  trusted_role text := new.raw_app_meta_data ->> 'role';
  client_role text := new.raw_user_meta_data ->> 'role';
  final_role public.user_role;
begin
  if trusted_role in ('admin', 'super_admin') then
    final_role := trusted_role::public.user_role;
  elsif client_role in ('brand', 'creator') then
    final_role := client_role::public.user_role;
  else
    -- Default to brand if signing up via brand portal with email/company
    final_role := 'brand'::public.user_role;
  end if;

  insert into public.profiles (
    id, role, status, name, mobile, email, company_name, terms_version, terms_accepted_at
  )
  values (
    new.id,
    final_role,
    case when final_role in ('admin', 'super_admin')
         then 'active'::public.account_status
         else 'active'::public.account_status end,
    new.raw_user_meta_data ->> 'name',
    coalesce(new.raw_user_meta_data ->> 'mobile', new.phone),
    new.email,
    new.raw_user_meta_data ->> 'company_name',
    new.raw_user_meta_data ->> 'terms_version',
    case when new.raw_user_meta_data ->> 'terms_version' is not null then now() end
  );
  return new;
end;
$$;

-- 2. Marketplace Creators catalog
create table if not exists public.creators (
  id text primary key,
  name text not null,
  category text not null,
  location text not null,
  city text not null,
  followers text not null,
  follower_count int not null,
  platform text not null,
  rating numeric(3,2) not null default 5.0,
  review_count int not null default 0,
  price_from int not null,
  deliverable text not null,
  quotes text[] not null default '{}',
  image text not null,
  top_creator boolean not null default false,
  bio text,
  gallery text[] not null default '{}',
  badges text[] not null default '{}',
  replies_within text not null default '2 hours',
  gender text,
  language text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 3. Bookable packages
create table if not exists public.creator_packages (
  id text primary key,
  creator_id text not null references public.creators(id) on delete cascade,
  title text not null,
  note text,
  price int not null,
  platform text not null,
  created_at timestamptz not null default now()
);

-- 4. Verified reviews
create table if not exists public.creator_reviews (
  id text primary key,
  creator_id text not null references public.creators(id) on delete cascade,
  name text not null,
  avatar text,
  stars int not null check (stars >= 1 and stars <= 5),
  date text not null,
  text text not null,
  created_at timestamptz not null default now()
);

-- 5. Saved creators / shortlist
create table if not exists public.saved_creators (
  user_id uuid not null references public.profiles(id) on delete cascade,
  creator_id text not null references public.creators(id) on delete cascade,
  saved_at timestamptz not null default now(),
  primary key (user_id, creator_id)
);

-- Access rules & RLS
alter table public.creators enable row level security;
alter table public.creator_packages enable row level security;
alter table public.creator_reviews enable row level security;
alter table public.saved_creators enable row level security;

-- Public can browse creators, packages, reviews
grant select on public.creators, public.creator_packages, public.creator_reviews to anon, authenticated;
grant select, insert, delete on public.saved_creators to authenticated;

create policy "anyone can view creators" on public.creators
  for select using (true);

create policy "anyone can view creator packages" on public.creator_packages
  for select using (true);

create policy "anyone can view creator reviews" on public.creator_reviews
  for select using (true);

create policy "users can view own saved creators" on public.saved_creators
  for select using (user_id = auth.uid());

create policy "users can save creators" on public.saved_creators
  for insert with check (user_id = auth.uid());

create policy "users can delete own saved creators" on public.saved_creators
  for delete using (user_id = auth.uid());

-- Seed creator catalog data matching UI specification
insert into public.creators (
  id, name, category, location, city, followers, follower_count, platform, rating, review_count, price_from, deliverable, quotes, image, top_creator, bio, gallery, badges, replies_within, gender, language
) values
(
  'ananya-rao',
  'Ananya Rao',
  'Beauty, Skincare',
  'Bengaluru',
  'Bengaluru',
  '48.2k',
  48200,
  'Instagram',
  4.9,
  42,
  8000,
  '1 Instagram Reel (30–45 sec)',
  array['Delivered two days early', 'Great with brand guidelines'],
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80',
  true,
  'Beauty and clean skincare creator based in Bengaluru. Passionate about authentic ingredient breakdowns, sustainable beauty, and everyday morning routines. 5+ years partnering with D2C cosmetics and skincare brands.',
  array[
    'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=800&q=80'
  ],
  array['Top Creator', 'Replies within 2 hours', 'High Engagement'],
  '2 hours',
  'female',
  'English, Kannada'
),
(
  'rohan-verma',
  'Rohan Verma',
  'Tech & Gadgets',
  'Bengaluru',
  'Bengaluru',
  '124.5k',
  124500,
  'YouTube',
  4.95,
  88,
  15000,
  '1 YouTube Dedicated Review (8–10 min)',
  array['Incredible camera work', 'Clear audio and thorough testing'],
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=600&q=80',
  true,
  'Gadget enthusiast, engineer, and video producer. In-depth, honest tech reviews covering smartphones, audio gear, developer desk setups, and emerging AI hardware.',
  array[
    'https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80'
  ],
  array['Top Creator', 'Verified Tech Reviewer'],
  '1 hour',
  'male',
  'English, Hindi'
),
(
  'neha-sharma',
  'Neha Sharma',
  'Fashion & Styling',
  'Mumbai',
  'Mumbai',
  '86.0k',
  86000,
  'Instagram',
  4.8,
  35,
  12000,
  '1 Instagram Reel + 3 Story frames',
  array['Effortless style transition', 'Drove 3x target link clicks'],
  'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=600&q=80',
  true,
  'Stylist and fashion consultant based in Mumbai. Curating lookbooks, festive Indo-western wear, and capsule wardrobe edits for conscious shoppers.',
  array[
    'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80'
  ],
  array['Top Creator', 'Fashion Week Alumni'],
  '3 hours',
  'female',
  'English, Hindi'
),
(
  'kabir-mehta',
  'Kabir Mehta',
  'Fitness & Health',
  'Delhi NCR',
  'Delhi NCR',
  '62.4k',
  62400,
  'Instagram',
  4.85,
  29,
  9500,
  '1 Reel workout integration with product placement',
  array['Clean fitness advice', 'Authentic audience trust'],
  'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=600&q=80',
  false,
  'Certified strength & conditioning coach. Empowering working professionals to stay fit with science-based 30-minute training routines and clean nutrition.',
  array[
    'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80',
    'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80'
  ],
  array['Certified Trainer', 'Prompt Delivery'],
  '4 hours',
  'male',
  'English, Hindi'
),
(
  'priya-iyer',
  'Priya Iyer',
  'Food & Dining',
  'Chennai',
  'Chennai',
  '34.1k',
  34100,
  'Instagram',
  4.9,
  24,
  5500,
  '1 Recipe Reel featuring brand ingredient',
  array['Mouthwatering food styling', 'Super easy recipe steps'],
  'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=600&q=80',
  false,
  'Traditional South Indian regional cuisine reimagined for busy modern kitchens. Focus on local, seasonal ingredients, cookware reviews, and heritage grains.',
  array[
    'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80'
  ],
  array['High Engagement', 'Culinary Specialist'],
  '2 hours',
  'female',
  'Tamil, English'
),
(
  'vikram-malhotra',
  'Vikram Malhotra',
  'Finance & Business',
  'Mumbai',
  'Mumbai',
  '210.0k',
  210000,
  'YouTube',
  4.92,
  112,
  25000,
  '1 YouTube Sponsoring Segment (60–90 sec)',
  array['Clear financial disclaimer', 'High conversion among professionals'],
  'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=600&q=80',
  true,
  'Chartered Accountant explaining personal finance, fintech tools, index investing, and tax planning without boring jargon. 10+ years in wealth advisory.',
  array[
    'https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80'
  ],
  array['Top Creator', 'SEBI Registered'],
  '1 hour',
  'male',
  'English, Hindi'
),
(
  'sneha-kapoor',
  'Sneha Kapoor',
  'Travel & Lifestyle',
  'Hyderabad',
  'Hyderabad',
  '73.8k',
  73800,
  'Instagram',
  4.78,
  31,
  11000,
  '1 Cinematic Travel Reel + 5 Stories',
  array['Breathtaking color grading', 'Delivered raw B-roll as bonus'],
  'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=600&q=80',
  false,
  'Solo backpacker and visual storyteller documenting boutique resorts, heritage architecture, and offbeat travel across India and Southeast Asia.',
  array[
    'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80'
  ],
  array['Cinematic Storyteller', 'Prompt Delivery'],
  '3 hours',
  'female',
  'English, Hindi, Telugu'
);

-- Seed Packages
insert into public.creator_packages (id, creator_id, title, note, price, platform) values
('pkg_1', 'ananya-rao', '1 Instagram Reel (30–45 sec)', 'Posted to your product feed with a tagged mention and swipe-up product link.', 8000, 'Instagram'),
('pkg_2', 'ananya-rao', '1 Reel + 3 Story Sequence', 'Includes product unboxing, 24-hr highlight pin, and discount code shoutout.', 12000, 'Instagram'),
('pkg_3', 'ananya-rao', 'Dedicated IG Carousel Post', '5 curated high-res slides with ingredient breakdowns and honest wear test.', 6500, 'Instagram'),
('pkg_4', 'rohan-verma', '1 YouTube Dedicated Review (8–10 min)', 'Thorough performance benchmark, deep feature review, and affiliate link in bio.', 25000, 'YouTube'),
('pkg_5', 'rohan-verma', 'YouTube Integrated Sponsor Segment (60–90 sec)', 'Placed in the first 3 minutes of an upcoming high-traffic tech comparison video.', 15000, 'YouTube'),
('pkg_6', 'neha-sharma', '1 Instagram Reel + 3 Story frames', 'Styling showcase featuring 3 complete looks with brand items.', 12000, 'Instagram'),
('pkg_7', 'kabir-mehta', '1 Reel workout integration with product placement', 'Natural workout routine featuring brand fitness apparel or nutrition.', 9500, 'Instagram'),
('pkg_8', 'priya-iyer', '1 Recipe Reel featuring brand ingredient', 'Step-by-step recipe video with ingredient focus and tagged brand recipe card.', 5500, 'Instagram'),
('pkg_9', 'vikram-malhotra', '1 YouTube Sponsoring Segment (60–90 sec)', 'Deep product walkthrough explaining fintech or investment advantages with pinned comment.', 25000, 'YouTube');

-- Seed Reviews
insert into public.creator_reviews (id, creator_id, name, avatar, stars, date, text) values
('rev_1', 'ananya-rao', 'Shreya S.', 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=120&q=80', 5, '2025-09-01', 'Delivered two days early! The lighting and presentation matched our brand guidelines flawlessly. We saw an immediate 20% spike in landing page visits.'),
('rev_2', 'ananya-rao', 'Gaurav K.', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=120&q=80', 5, '2025-08-15', 'Ananya was super communicative and understood the tone of our sustainable skincare launch immediately. Looking forward to our next quarterly campaign.'),
('rev_3', 'ananya-rao', 'Meera P.', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80', 4, '2025-07-20', 'Great reel quality and engagement. Only a minor delay on the first draft revision, but the final outcome was stellar.'),
('rev_4', 'rohan-verma', 'Amitabh R.', 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=120&q=80', 5, '2025-09-10', 'Rohan is hands down one of the most technical and credible tech creators in India. The video converted exceptionally well for our monitor launch.'),
('rev_5', 'neha-sharma', 'Radhika T.', 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=120&q=80', 5, '2025-08-28', 'Drove 3x target link clicks for our Diwali festive collection. Highly recommended for premium apparel brands.');
