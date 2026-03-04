-- Migration: Add profile fields to users
-- Date: 2026-02-09

-- Add company column
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS company VARCHAR(200);

-- Add role column  
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS role VARCHAR(100);

-- Add bio column
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS bio VARCHAR(1000);
