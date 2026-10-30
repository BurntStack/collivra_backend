-- Migration to remove all static image URLs from creators, deliverables, and reviews

UPDATE public.creators 
SET image = '', 
    gallery = '{}' 
WHERE image LIKE '%unsplash%' OR array_to_string(gallery, ',') LIKE '%unsplash%';

UPDATE public.deliverables 
SET preview_url = '' 
WHERE preview_url LIKE '%unsplash%';

UPDATE public.creator_reviews 
SET avatar = '' 
WHERE avatar LIKE '%unsplash%';
