-- Migration: Seed curated, high-resolution aesthetic imagery for female creators matching their categories

-- 1. Ananya Rao (Beauty & Skincare)
UPDATE public.creators 
SET image = 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80',
    gallery = ARRAY[
      'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=800&q=80'
    ]
WHERE id = 'ananya-rao';

-- 2. Neha Sharma (Fashion & Styling)
UPDATE public.creators 
SET image = 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=800&q=80',
    gallery = ARRAY[
      'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=800&q=80'
    ]
WHERE id = 'neha-sharma';

-- 3. Priya Iyer (Food & Dining)
UPDATE public.creators 
SET image = 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80',
    gallery = ARRAY[
      'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=800&q=80'
    ]
WHERE id = 'priya-iyer';

-- 4. Sneha Kapoor (Travel & Lifestyle)
UPDATE public.creators 
SET image = 'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=800&q=80',
    gallery = ARRAY[
      'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80',
      'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=800&q=80'
    ]
WHERE id = 'sneha-kapoor';

-- 5. Reviewer Avatars
UPDATE public.creator_reviews SET avatar = 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=200&q=80' WHERE id = 'rev_1';
UPDATE public.creator_reviews SET avatar = 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=200&q=80' WHERE id = 'rev_3';
UPDATE public.creator_reviews SET avatar = 'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=200&q=80' WHERE id = 'rev_5';

-- 6. Deliverable Previews
UPDATE public.deliverables SET preview_url = 'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80' WHERE creator_id = 'ananya-rao';
UPDATE public.deliverables SET preview_url = 'https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80' WHERE creator_id = 'neha-sharma';
