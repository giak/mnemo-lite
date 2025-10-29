# EPIC-05: MnemoLite UI for Local Exploration & Interaction

*   **Goal (Ω):** Provide a functional and intuitive web interface for users (Developers, Analysts, Testers) to explore, search, filter, and potentially interact with MnemoLite memories stored locally via PostgreSQL. The UI should leverage HTMX for server interactions and Alpine.js for minor client-side enhancements, aligning with the documented architecture (`docs/ui_architecture.md`).
*   **User Roles:** Analyst, Developer, Tester.
*   **Key Value Proposition:** Enable easier debugging, testing, understanding, and demonstration of MnemoLite's capabilities without solely relying on API calls or direct database queries.

---

## Initial User Stories (Brainstorm - Φ)

*(Needs refinement based on INVEST principles)*

**Feature Area: Dashboard / Basic View (UC3)**

*   **US-05.1:** As an Analyst, I want to load the main UI page (`/ui/`) and see a list of the 10 most recent events (displaying timestamp, ID, and a snippet of content/metadata), so that I can get a quick overview of the latest memory activity.
*   **US-05.2:** As a Developer, I want the main event list to have a "Load More" button (or simple pagination links) that uses HTMX to fetch and append/replace the next set of events, so that I can browse beyond the initial view without a full page reload. (HTMX)
*   **US-05.3:** As an Analyst, I want basic visual distinction between different `event_type` entries in the list (e.g., different icons or background colours defined via CSS classes applied server-side), so that I can quickly scan for specific types of events.

**Feature Area: Search & Filtering (UC2 & UC3)**

*   **US-05.4:** As a Developer, I want a dedicated Search page (`/ui/search`) accessible from the main navigation, so that I have a focused area for querying the memory.
*   **US-05.5:** As an Analyst, I want input fields on the Search page to filter events by a **date range** (start/end date), so that I can isolate events within a specific timeframe. (HTMX submit, potentially Alpine.js for date picker UI enhancement).
*   **US-05.6:** As an Analyst, I want an input field on the Search page to filter events by **metadata** (e.g., entering `{"event_type": "decision"}` or maybe simpler key/value inputs), so that I can find events based on specific tags or attributes. (HTMX submit, Alpine.js could help manage adding/removing multiple key/value filter criteria dynamically).
*   **US-05.7:** As an Analyst, I want a text input field on the Search page to perform a **similarity search** based on content, so that I can find memories semantically related to my query text. (HTMX submit).
*   **US-05.8:** As a Developer, I want the search results area to be updated via HTMX after submitting a search query, displaying a list of matching events similar to the dashboard view (timestamp, ID, snippet, maybe similarity score), so that the search feels interactive.
*   **US-05.9:** As an Analyst, I want active filters (date range, metadata) to be clearly displayed above the search results, so that I know what criteria are currently applied. (Alpine.js could potentially manage the visual state of filter input elements).

**Feature Area: Event Detail View (UC3)**

*   **US-05.10:** As an Analyst, I want to click on an event's ID or summary in any list (dashboard, search results) and see its full details loaded dynamically (perhaps in a modal or a dedicated section via HTMX), so that I can examine a specific memory without leaving the current context entirely. (HTMX `hx-get` to a detail endpoint).
*   **US-05.11:** As a Developer, I want the event detail view to clearly display the full `content` and `metadata` JSON objects in a readable format (e.g., pre-formatted text block), so that I can easily inspect the raw data.
*   **(Stretch Goal) US-05.12:** As an Analyst, I want the event detail view to show a list of directly linked events (incoming/outgoing edges from the `edges` table, max 1-hop initially), so that I can see immediate relationships. (Requires backend logic and HTMX loading).

**(Lower Priority) Feature Area: Basic Ingestion (UC1 - for Testing)**

*   **US-05.13:** As a Tester, I want a simple form (perhaps on a separate page or section) where I can paste JSON for `content` and `metadata` and submit it to create a new event via HTMX, so that I can quickly add test data through the UI. (HTMX `hx-post`).

--- 