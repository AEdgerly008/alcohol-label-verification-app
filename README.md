# Sample Labels

Place test label images in this directory for development and testing.

## Suggested sources

1. **TTB COLA Public Registry** — Real approved labels:
   https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do

2. **AI image generation** — Generate synthetic labels with tools like DALL·E or Midjourney.
   Prompt example: "alcohol bottle label for a bourbon whiskey, showing brand name OLD TOM DISTILLERY,
   Kentucky Straight Bourbon Whiskey, 45% Alc./Vol., 750 mL, government warning statement, clean product photography"

3. **Included test cases** — The repo includes a few synthetic labels to cover edge cases:
   - `sample_pass.jpg` — A clean label that should PASS all checks
   - `sample_fail_warning.jpg` — A label with "Government Warning" (title case) instead of "GOVERNMENT WARNING:"
   - `sample_needs_review.jpg` — A label with a brand name formatted differently from the application

## Notes

- Images should be at least 800×600px for reliable OCR
- JPG, PNG, and WEBP are all supported
- The app handles angled or glare-affected images but accuracy improves with clean, straight-on photos
