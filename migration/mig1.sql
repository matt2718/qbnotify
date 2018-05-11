ALTER TABLE notification ADD unit VARCHAR(8) NULL;
UPDATE notification SET unit = 'm' WHERE type = 'C';
