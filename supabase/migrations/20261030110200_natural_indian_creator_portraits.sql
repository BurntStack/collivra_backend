-- Migration: Update creator portraits with authentic, real, and natural Indian female creator photos

-- 1. Ananya Rao (Beauty, Skincare) - Authentic natural Indian portrait
UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1617627143750-d86bc21e42bb?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=800&q=80']
WHERE id = 'ananya-rao';

-- 2. Neha Sharma (Fashion & Styling) - Authentic natural Indian creator portrait
UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1609357605129-26f69add5d6e?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80']
WHERE id = 'neha-sharma';

-- 3. Sneha Kapoor (Travel & Lifestyle) - Natural travel portrait
UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1614289371518-722f2615943d?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80']
WHERE id = 'sneha-kapoor';

-- 4. Priya Iyer (Food & Dining) - Warm authentic portrait
UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1567532939604-b6b5b0db2604?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80']
WHERE id = 'priya-iyer';

-- 5. Non-seed creator cards with authentic, natural Indian female portraits
UPDATE public.creators SET name = 'Aanya Sen', image = 'https://images.unsplash.com/photo-1616766098946-e4fabb7d6da0?auto=format&fit=crop&w=800&q=80' WHERE id = '0a166fd7-2d21-43fa-bfb1-f3436a919ff5';
UPDATE public.creators SET name = 'Dia Mirza', image = 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=800&q=80' WHERE id = '13b04195-b854-43f6-bf87-bdfd5beb543f';
UPDATE public.creators SET name = 'Rhea Pillai', image = 'https://images.unsplash.com/photo-1589156280159-27698a70f29e?auto=format&fit=crop&w=800&q=80' WHERE id = '514c1426-135d-4dbe-8ed8-26c81d60ebf5';
UPDATE public.creators SET name = 'Tara Sutaria', image = 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&w=800&q=80' WHERE id = 'b5a3a91f-9467-4269-be78-c2063d758bda';
UPDATE public.creators SET name = 'Kriti Sanon', image = 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=800&q=80' WHERE id = 'c3d599ff-c559-40f1-9c98-70e7830d4b33';
UPDATE public.creators SET name = 'Sara Ali', image = 'https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?auto=format&fit=crop&w=800&q=80' WHERE id = 'c89d4a51-8543-4ad7-8291-ea8e7c575201';
UPDATE public.creators SET name = 'Zoya Akhtar', image = 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=800&q=80' WHERE id = 'ce432931-bc99-4b06-be5e-c3bee88ab03a';
UPDATE public.creators SET name = 'Isha Ambani', image = 'https://images.unsplash.com/photo-1607746882042-944635dfe10e?auto=format&fit=crop&w=800&q=80' WHERE id = 'cf12d64e-4fc3-41f9-85d8-e06615f86621';
