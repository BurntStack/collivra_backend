-- Update all creators with high-resolution, vibrant portraits matching their category

-- 1. Seed creators
UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1519389950473-47ba0277781c?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=800&q=80']
WHERE id = 'rohan-verma';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=800&q=80']
WHERE id = 'vikram-malhotra';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80']
WHERE id = 'kabir-mehta';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1512496015851-a90fb38ba796?auto=format&fit=crop&w=800&q=80']
WHERE id = 'ananya-rao';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&w=800&q=80']
WHERE id = 'neha-sharma';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80', 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80']
WHERE id = 'sneha-kapoor';

UPDATE public.creators SET 
  image = 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=800&q=80',
  gallery = ARRAY['https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80']
WHERE id = 'priya-iyer';

-- 2. Non-seed cards with beautiful lifestyle creator portraits
UPDATE public.creators SET name = 'Aanya Sen', image = 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=800&q=80' WHERE id = '0a166fd7-2d21-43fa-bfb1-f3436a919ff5';
UPDATE public.creators SET name = 'Dia Mirza', image = 'https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=800&q=80' WHERE id = '13b04195-b854-43f6-bf87-bdfd5beb543f';
UPDATE public.creators SET name = 'Rhea Pillai', image = 'https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=800&q=80' WHERE id = '514c1426-135d-4dbe-8ed8-26c81d60ebf5';
UPDATE public.creators SET name = 'Tara Sutaria', image = 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=800&q=80' WHERE id = 'b5a3a91f-9467-4269-be78-c2063d758bda';
UPDATE public.creators SET name = 'Kriti Sanon', image = 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&w=800&q=80' WHERE id = 'c3d599ff-c559-40f1-9c98-70e7830d4b33';
UPDATE public.creators SET name = 'Sara Ali', image = 'https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?auto=format&fit=crop&w=800&q=80' WHERE id = 'c89d4a51-8543-4ad7-8291-ea8e7c575201';
UPDATE public.creators SET name = 'Zoya Akhtar', image = 'https://images.unsplash.com/photo-1520813792240-56fc4a3765a7?auto=format&fit=crop&w=800&q=80' WHERE id = 'ce432931-bc99-4b06-be5e-c3bee88ab03a';
UPDATE public.creators SET name = 'Isha Ambani', image = 'https://images.unsplash.com/photo-1509967419530-da38b4704bc6?auto=format&fit=crop&w=800&q=80' WHERE id = 'cf12d64e-4fc3-41f9-85d8-e06615f86621';
