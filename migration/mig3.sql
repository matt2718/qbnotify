ALTER TABLE user ADD COLUMN fs_uniquifier VARCHAR(8) NOT NULL DEFAULT "asdf";
UPDATE user SET fs_uniquifier = hex(randomblob(16));
