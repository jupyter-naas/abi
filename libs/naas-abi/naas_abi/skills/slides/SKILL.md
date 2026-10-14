---
name: Slides
description: Presentations in Nexus Slides. Hand the deck to SlidesAgent and edit the open presentation.
when_to_use: The user wants slides, a deck, or a presentation.
---

# Slides

Nexus Slides keeps the deck as presentation HTML. A PowerPoint file is only an export of that HTML, not the file you author.

Hand the deck to SlidesAgent and write the open presentation HTML, not a PowerPoint file.

When no deck is open, call create_slides_project with a short title from the brief. For anything time-sensitive, call web_search before the first write (a few queries, then stop). Write the deck with write_slides_sections or write_slides_deck. Use replace_in_slides_deck for a single copy change. Do not dump deck HTML into the chat. Report the title and what changed.
