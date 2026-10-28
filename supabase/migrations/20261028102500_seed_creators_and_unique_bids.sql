-- Migration: Mark Vikram, Priya, Kabir and Sneha as is_seed, and unique index for campaign bids
UPDATE public.creators
SET is_seed = true
WHERE id IN ('vikram-malhotra', 'priya-iyer', 'kabir-mehta', 'sneha-kapoor');

-- Enforce one bid per creator per campaign via unique index
CREATE UNIQUE INDEX IF NOT EXISTS campaign_bids_campaign_creator_idx
ON public.campaign_bids (campaign_id, creator_id);
