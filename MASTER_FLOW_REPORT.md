You are working on my existing project: PROMOPILOT.

IMPORTANT:
Do NOT rebuild the application from scratch.
Do NOT create a separate demo.
Do NOT replace the existing scraper, backend, database, frontend, sidebar, or current UI unnecessarily.

First inspect the ENTIRE existing codebase:
- frontend
- backend
- database models
- API routes
- services
- scraper
- AI generation
- media handling
- publishing
- scheduling
- settings
- existing migrations
- existing environment variables

Understand the current architecture and then implement ALL requirements below in the existing project.

The goal is to make the complete end-to-end AI social media promotion workflow actually work.

==================================================
1. FINAL REQUIRED WORKFLOW
==================================================

The application must work as:

Website
  ↓
Website Scraper
  ↓
Properties
  ↓
Property Approval
  ↓
Approved Property
  ↓
AI Content Generation
  ↓
3 Posts + 3 Stories per day
  ↓
AI Image / Video Generation
  ↓
Human Approval OR Automation
  ↓
Approve & Post OR Approve & Schedule
  ↓
Feeds / Calendar
  ↓
Publishing Logs

For Stories:

Approved Property
  ↓
Story Content
  ↓
10-second vertical video
  ↓
Human Approval OR Automation
  ↓
Publish / Schedule
  ↓
Feeds

==================================================
2. DO NOT BREAK CURRENT SCRAPING
==================================================

The existing website scraping functionality is already working.

Preserve it.

When scraping a website:
- scrape property/content information
- scrape title
- description
- location
- price if available
- amenities if available
- source URL
- scraped images
- other useful information already supported by the existing scraper

The scraped items must appear in the existing Properties section.

Do not remove or replace the current scraper unless absolutely necessary.

==================================================
3. PROPERTY APPROVAL
==================================================

Currently scraped items appear in Properties but there is no proper Approve/Reject workflow.

Add it.

Every property must have:

approval_status:
- PENDING
- APPROVED
- REJECTED

Default:
PENDING

Properties UI must show:

[Approve]
[Reject]

For approved:

✓ Approved

For rejected:

✕ Rejected

Add confirmation/loading states.

Reject should optionally allow a rejection reason.

Do not allow rejected properties to generate content.

In HUMAN APPROVAL mode:
content generation must require property approval.

In AUTOMATION mode:
the system may automatically approve eligible scraped properties.

==================================================
4. PROPERTY DETAIL
==================================================

Property detail page/modal must show:

- Property name
- Location
- Description
- Price
- Amenities
- Source website
- Source URL
- Original scraped images
- AI-generated replacement images if required
- Approval status
- Media status
- Content generation status

Broken images must never display as broken-image icons.

Show:

"Image unavailable — generating replacement"

while replacement generation is running.

==================================================
5. IMAGE PROBLEM / AI FALLBACK
==================================================

Some scraped images currently do not display correctly.

Fix this.

For every scraped image:

1. Check URL.
2. Download/validate the image.
3. Verify HTTP response.
4. Verify content type.
5. Verify that the image can actually be decoded.
6. If valid, use the original image.
7. If invalid, unavailable, blocked, 403, timeout, malformed, or broken:
   automatically generate a replacement image using AI.

IMPORTANT:

Do NOT use Groq as the image-generation provider.

Groq can be used for:
- text generation
- summarization
- caption generation
- prompt generation
- content generation

Use OpenAI image generation for actual AI image generation.

Use the existing OpenAI configuration if already present.

If the project already has an image-generation abstraction, extend it rather than creating duplicate code.

==================================================
6. AI IMAGE GENERATION
==================================================

Generate replacement images using the scraped property context.

The AI image prompt must use:

- property name
- location
- description
- amenities
- category
- available visual information

Example internal prompt:

"Create a realistic premium tourism photograph based only on the supplied property information.

Property:
{{property_name}}

Location:
{{location}}

Description:
{{description}}

Amenities:
{{amenities}}

Create a realistic travel/tourism promotional image.

Do not invent identifiable facts.
Do not add text.
Do not add logos.
Do not add watermarks.
Do not create fake signage."

Do not generate generic random travel images.

The generated image should visually match the scraped context.

==================================================
7. PERSISTENT MEDIA STORAGE
==================================================

IMPORTANT:

Render local filesystem is NOT reliable permanent storage.

Do not depend on:

backend/generated_media/

as permanent production storage.

The application must use a media-storage abstraction.

For local development:
local filesystem may be used.

For production:
use persistent object/media storage configured through environment variables.

If the project already has a storage provider, reuse it.

Otherwise implement a clean storage abstraction that can support an external object-storage provider.

The database must store:

storage_url
mime_type
media_type
provider
prompt
generation_status
created_at

Do NOT store huge image/video binary data directly inside PostgreSQL.

==================================================
8. GENERATED MEDIA DATABASE
==================================================

Create or update a GeneratedMedia model/table.

Required fields:

id
property_id
content_id
media_type
provider
prompt
storage_url
thumbnail_url
mime_type
generation_status
created_at
updated_at

media_type:

IMAGE
VIDEO

generation_status:

PENDING
GENERATING
COMPLETED
FAILED

Every generated image must create a GeneratedMedia record.

Every generated video must create a GeneratedMedia record.

Every post/story that uses media must reference that media.

==================================================
9. CONTENT GENERATION
==================================================

After a property is approved, generate social media content.

Default daily generation:

3 POSTS
3 STORIES

These must be DIFFERENT from each other.

Do not generate the same caption six times.

==================================================
10. THREE POSTS
==================================================

Generate 3 different post variants.

POST 1:
Property Highlight

Focus on:
- property
- amenities
- unique features
- stay experience

POST 2:
Destination / Location

Focus on:
- location
- nearby attractions
- destination experience
- travel inspiration

POST 3:
Emotional / Inspirational

Focus on:
- vacation experience
- relaxation
- travel motivation
- emotional storytelling

Each post should have:

title
caption
CTA
hashtags
platform
variant_number

Use the existing supported platforms in the project.

==================================================
11. THREE STORIES
==================================================

Generate 3 different stories per property/day.

Each story must contain:

hook
short message
CTA
visual concept

Stories must be short and social-media friendly.

Example:

Story 1:
"Looking for your next escape?"

Story 2:
"Wake up somewhere worth remembering."

Story 3:
"Ready for your next stay?"

But generate the actual text dynamically from the approved property.

==================================================
12. SOCIAL CONTENT DATABASE
==================================================

Create/update the content model.

Required:

id
property_id
content_type
platform
variant_number
title
caption
hashtags
cta
media_id
approval_status
publish_status
scheduled_at
published_at
created_at
updated_at

content_type:

POST
STORY

approval_status:

PENDING
APPROVED
REJECTED

publish_status:

DRAFT
SCHEDULED
PUBLISHED
FAILED

Do not duplicate existing tables if equivalent tables already exist.
Modify the existing models when appropriate.

==================================================
13. CONTENT PAGE
==================================================

The existing Content page must display generated content.

Organize it clearly by:

Today
Upcoming
Previous

For every post show:

- preview
- platform
- title
- caption
- hashtags
- media
- approval status
- publishing status

Buttons:

[Approve & Post]
[Approve & Schedule]
[Reject]

For stories show:

- video preview
- story text
- duration
- platform
- status

Buttons:

[Approve & Post]
[Approve & Schedule]
[Reject]

==================================================
14. APPROVE & POST
==================================================

When user clicks:

Approve & Post

do all required operations.

Set:

approval_status = APPROVED
publish_status = PUBLISHED

Create a PublishLog record.

Store:

content_id
platform
status
published_at
external_post_id if available
error if failed

Then the content must appear in Feeds.

If the project currently uses simulated publishing for demo purposes, preserve that behavior but make the database/publishing flow realistic and clearly logged.

Do not pretend that a real social media API was called if it was not.

==================================================
15. APPROVE & SCHEDULE
==================================================

When user clicks:

Approve & Schedule

open a scheduling dialog.

Allow:

date
time
platform

On confirmation:

approval_status = APPROVED
publish_status = SCHEDULED
scheduled_at = selected datetime

The item must appear in:

Calendar
Feeds

with:

Scheduled

status.

==================================================
16. REJECT CONTENT
==================================================

When user clicks Reject:

show optional rejection reason.

Set:

approval_status = REJECTED

Rejected content must NEVER be published.

Rejected content must not appear as published in Feeds.

==================================================
17. STORY VIDEO GENERATION
==================================================

Every generated story must have a 10-second vertical video.

Required:

1080x1920
9:16
10 seconds
MP4

For the demo, do NOT require an expensive AI video-generation API.

Use:

AI-generated image
+
FFmpeg
+
subtle zoom/pan animation
+
text overlays
+
CTA

Example timeline:

0-3 seconds:
Hook

3-7 seconds:
Main message

7-10 seconds:
CTA

Generate a professional travel/social-media style video.

The video must be stored using the same persistent media-storage system.

==================================================
18. VIDEO DATABASE
==================================================

For every story video:

GeneratedMedia:

media_type = VIDEO
mime_type = video/mp4
generation_status = COMPLETED
storage_url = persistent URL

The SocialPost/Content record must have:

media_id

linked to the GeneratedMedia record.

There must NEVER be a generated video that exists only on the server filesystem without a database record.

==================================================
19. FEEDS PAGE
==================================================

The existing Feeds section must become the final publishing view.

Show:

Published
Scheduled
Failed

Published card:

- platform
- property
- media
- caption
- published date/time
- status

Scheduled:

- platform
- media
- scheduled date/time
- status

Failed:

- error
- retry button

When content is approved and posted:

Content
  ↓
Publish
  ↓
Feeds

When content is approved and scheduled:

Content
  ↓
Schedule
  ↓
Calendar
  ↓
Feeds

==================================================
20. AUTOMATION / HUMAN APPROVAL
==================================================

The Settings page must contain:

Approval Mode

OPTIONS:

Human Approval
Automation

Default:

Human Approval

Store this setting persistently in the database/configuration.

==================================================
21. HUMAN APPROVAL MODE
==================================================

When:

approval_mode = HUMAN

workflow:

Scrape
↓
Property PENDING
↓
Human approves property
↓
Generate 3 posts + 3 stories
↓
Content PENDING
↓
Human approves content
↓
Post or Schedule
↓
Feeds

Nothing should automatically publish.

==================================================
22. AUTOMATION MODE
==================================================

When:

approval_mode = AUTOMATION

workflow:

Scrape
↓
AI validation
↓
Auto-approve property
↓
Generate content
↓
Generate media
↓
Auto-approve content
↓
Publish / schedule according to configured automation behavior
↓
Feeds

No manual approval should be required.

Every automatic action must still be logged.

==================================================
23. AUTOMATION LOGGING
==================================================

Reuse the existing AgentRun / logging architecture if available.

Log:

PROPERTY_SCRAPED
PROPERTY_AUTO_APPROVED
PROPERTY_APPROVED
PROPERTY_REJECTED

CONTENT_GENERATED
CONTENT_AUTO_APPROVED
CONTENT_APPROVED
CONTENT_REJECTED

IMAGE_GENERATION_STARTED
IMAGE_GENERATED
IMAGE_GENERATION_FAILED

VIDEO_GENERATION_STARTED
VIDEO_GENERATED
VIDEO_GENERATION_FAILED

POST_PUBLISHED
POST_SCHEDULED
POST_FAILED

Each log should include:

action
entity_type
entity_id
status
timestamp
error if any
mode

==================================================
24. APPROVALS PAGE
==================================================

The existing sidebar already contains:

Dashboard
Calendar
Content
Approvals
Properties
Feeds
Logs
Settings

Keep this navigation.

Make Approvals actually functional.

Approvals page should have:

TAB 1:
Properties

TAB 2:
Content

Properties tab:

Pending scraped properties
Approve
Reject

Content tab:

Pending posts/stories
Approve & Post
Approve & Schedule
Reject

==================================================
25. DASHBOARD
==================================================

Update dashboard counters.

Show:

Scraped Properties
Pending Property Approval
Approved Properties
Rejected Properties

Content Pending Review
Approved Content
Scheduled
Published
Rejected

Also show automation mode:

Human Approval
or
Automation

==================================================
26. SETTINGS
==================================================

Settings should show:

Approval Mode

Human Approval
Automation

Content Generation:

Posts per day: 3
Stories per day: 3

Story duration:
10 seconds

These should have sensible defaults.

If easy, make them configurable.

==================================================
27. DUPLICATE PREVENTION
==================================================

Do not generate duplicate content for the same property/day.

Before generation:

check whether content already exists for:

property_id
generation_date
content_type
variant_number

If already generated, do not generate duplicates.

Allow explicit regeneration through a separate action if necessary.

==================================================
28. API
==================================================

Inspect existing routes first.

Reuse existing endpoints when possible.

The final API should support equivalent functionality to:

GET /api/properties
GET /api/properties/{id}

POST /api/properties/{id}/approve
POST /api/properties/{id}/reject

POST /api/properties/{id}/generate-content

GET /api/content
GET /api/content/{id}

POST /api/content/{id}/approve
POST /api/content/{id}/reject

POST /api/content/{id}/publish
POST /api/content/{id}/schedule

GET /api/feeds

GET /api/media/{id}

POST /api/media/generate-image
POST /api/media/generate-video

GET /api/settings
PUT /api/settings/approval-mode

Do NOT create duplicate APIs if equivalent routes already exist.

==================================================
29. DATABASE RELATIONSHIPS
==================================================

Final relationship should be:

Property
  ↓
Content
  ↓
GeneratedMedia
  ↓
PublishLog

Property:

has many Content

Content:

belongs to Property
has optional GeneratedMedia

GeneratedMedia:

belongs to Content
belongs to Property

PublishLog:

belongs to Content

Use proper foreign keys.

Do not store duplicated media information unnecessarily.

==================================================
30. RENDER DEPLOYMENT
==================================================

The application must work on Render.

Do not assume local filesystem is persistent.

Use environment variables for:

DATABASE_URL
OPENAI_API_KEY
GROQ_API_KEY if existing
IMAGE_MODEL
LLM_MODEL
MEDIA_STORAGE configuration
FRONTEND_URL
other existing environment variables

Never hard-code API keys.

Do not commit secrets.

==================================================
31. DATABASE MIGRATIONS
==================================================

Before modifying the database:

Inspect existing models and schema.

Do NOT:

drop_all()
drop database
delete existing records
recreate the whole database destructively

Create safe migrations.

Preserve existing scraped properties and existing content.

If a migration system already exists, use it.

If the current project has a lightweight schema migration mechanism, extend it safely.

==================================================
32. FRONTEND UX
==================================================

Keep the existing visual design.

Do not redesign the entire dashboard.

Add:

loading states
empty states
error states
success notifications
confirmation dialogs
media previews
video previews
approval status badges

Buttons must clearly communicate actions.

Examples:

Approve
Reject
Approve & Post
Approve & Schedule
Retry
Generate
Regenerate

==================================================
33. MEDIA PREVIEW
==================================================

Images:

display image preview.

Videos:

display HTML video player with controls.

Do not expose raw local filesystem paths to the browser in production.

Use the persistent media URL.

==================================================
34. ERROR HANDLING
==================================================

Every asynchronous operation must handle:

loading
success
failure
retry

Examples:

"Generating image..."
"Image generated successfully."
"Image generation failed. Retry."

"Generating video..."
"Video generated successfully."
"Video generation failed. Retry."

"Publishing..."
"Published successfully."
"Publishing failed. Retry."

Never silently fail.

==================================================
35. SECURITY
==================================================

Do not expose:

API keys
database credentials
storage credentials

to the frontend.

AI generation must happen server-side.

Validate all IDs.

Protect admin endpoints using the project's existing authentication.

Do not allow arbitrary users to publish content unless authorized.

==================================================
36. END-TO-END TEST
==================================================

After implementation, perform a complete test.

TEST A:

Scrape website.

Expected:
new property appears in Properties.

TEST B:

Use a broken/unavailable scraped image.

Expected:
AI replacement image generated.

TEST C:

Approve property.

Expected:
approval_status = APPROVED.

TEST D:

Generate content.

Expected:
3 different posts
+
3 different stories.

TEST E:

Story generation.

Expected:
10-second 1080x1920 MP4.

TEST F:

Verify database.

Every generated image/video must have:

GeneratedMedia record
storage_url
mime_type
media_type

Every content record requiring media must have:

media_id

TEST G:

Human mode.

Expected:
property requires approval.
content requires approval.
nothing automatically publishes.

TEST H:

Approve & Post.

Expected:
publish_status = PUBLISHED
PublishLog created
item visible in Feeds.

TEST I:

Approve & Schedule.

Expected:
publish_status = SCHEDULED
scheduled_at populated
item visible in Calendar and Feeds.

TEST J:

Reject.

Expected:
REJECTED
no publishing.

TEST K:

Automation mode.

Expected:

Scrape
→ auto approve
→ content generation
→ media generation
→ auto approve
→ publish/schedule
→ Feeds

TEST L:

Restart backend.

Expected:
generated media references still work.
database records still exist.
no generated media disappears because of local Render storage.

==================================================
37. IMPORTANT CODE QUALITY RULES
==================================================

Before writing new code:

1. Search for existing equivalent implementation.
2. Reuse existing services/models/routes.
3. Avoid duplicate models.
4. Avoid duplicate APIs.
5. Avoid duplicate storage systems.
6. Keep current architecture.
7. Keep current UI style.
8. Keep existing scraper.
9. Keep existing authentication.
10. Keep existing scheduling functionality where possible.

Use clean service separation:

scraper service
AI content service
image generation service
video generation service
media storage service
publishing service
approval service

Do not put all logic inside API route handlers.

==================================================
38. IMPORTANT IMAGE PROVIDER RULE
==================================================

Groq is NOT an image-generation provider.

Use:

TEXT:
existing Groq/OpenAI text model

IMAGE:
OpenAI image generation

VIDEO:
FFmpeg using generated image + motion/text

Do not attempt to send image-generation requests to Groq.

==================================================
39. IMPORTANT RENDER STORAGE RULE
==================================================

Do not treat:

backend/generated_media/

as permanent production storage.

It can be used temporarily for processing.

Final media must be uploaded to persistent storage.

PostgreSQL stores the metadata and URL.

==================================================
40. FINAL DATABASE CHECK
==================================================

For every generated post/story verify:

content.id exists
property_id exists
media_id exists when media is required

Then:

GeneratedMedia.id exists
GeneratedMedia.storage_url exists
GeneratedMedia.mime_type exists

Then:

PublishLog.content_id exists after publish/schedule.

No orphan media should be silently created.

No published content should reference missing media.

==================================================
41. FINAL DEFINITION OF DONE
==================================================

Do NOT tell me "completed" until the following works:

Website scraping
↓
Properties
↓
Approve / Reject
↓
Approved property
↓
AI generates 3 different posts
↓
AI generates 3 different stories
↓
Images generated when scraped images are unavailable
↓
10-second story videos generated
↓
Generated images/videos persisted
↓
Media database records created
↓
Content references media correctly
↓
Human Approval mode works
↓
Automation mode works
↓
Approve & Post works
↓
Approve & Schedule works
↓
Reject works
↓
Feeds works
↓
Calendar works
↓
Logs work
↓
Restart backend
↓
Media/database references still work

==================================================
42. EXECUTION INSTRUCTIONS
==================================================

Work directly on the existing codebase.

First inspect the project and identify:
- current frontend framework
- current backend framework
- current database
- existing scraper
- existing property model
- existing content model
- existing media implementation
- existing publishing implementation
- existing scheduler
- existing settings implementation

Then implement all required changes.

After implementation:

1. Run backend.
2. Run frontend.
3. Run migrations.
4. Run tests.
5. Test APIs.
6. Test frontend workflow.
7. Test image generation.
8. Test video generation.
9. Test database relationships.
10. Test human mode.
11. Test automation mode.
12. Fix all errors.
13. Verify no existing functionality was broken.

If an external service such as OpenAI image generation or persistent media storage is not configured, implement the integration completely and clearly report ONLY the missing environment variable/configuration required. Do not replace the feature with fake success.

At the end provide:

A. Files changed
B. Database changes
C. APIs added/updated
D. Environment variables required
E. Tests performed
F. Any remaining configuration needed
G. Exact commands to run the application

Most importantly:

DO NOT just modify the UI.

This is an END-TO-END backend + database + AI + media + frontend workflow implementation.

Make the actual application work.