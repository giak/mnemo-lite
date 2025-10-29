# User Stories for EPIC-05: MnemoLite UI for Local Exploration & Interaction

**Version**: 1.0.0
**Date**: 2025-05-04

**Epic Reference**: `EPIC-05_UI_Exploration_MnemoLite.md`

**Note**: These are initial user stories based on the brainstorm. They may require further refinement, splitting, and estimation based on the INVEST principles as development progresses.

---

## Feature Area: UI Foundation & Setup

*   **US-05.0: Setup UI Foundation (Routes, Templates, Basic Config)**
    *   **As a** Developer,
    *   **I want** to set up the basic FastAPI routing, Jinja2 templating configuration, static file serving, and necessary dependencies for the UI,
    *   **So that** subsequent UI stories have a stable foundation to build upon.
    *   **Tasks:**
        *   `- [ ]` Configure Jinja2Templates in `main.py`.
        *   `- [ ]` Configure StaticFiles mounting in `main.py`.
        *   `- [ ]` Create base UI router in `routes/ui/base.py`.
        *   `- [ ]` Include the UI router in `main.py` (e.g., under `/ui` prefix).
        *   `- [ ]` Ensure `templates/base.html` exists and includes HTMX/Alpine.js CDN links.
        *   `- [ ]` Create basic empty `static/css/style.css` and `static/js/script.js` (optional, for structure).
        *   `- [ ]` Write a simple test verifying the `/ui/` route returns 200 OK and contains expected base HTML elements.
    *   **Acceptance Criteria:**
        *   `- [ ]` FastAPI correctly serves static files from the `static` directory.
        *   `- [ ]` FastAPI is configured to use the `templates` directory for Jinja2.
        *   `- [ ]` The UI router (`routes/ui/base.py`) is correctly included in the main FastAPI app.
        *   `- [ ]` Accessing the base UI route (e.g., `http://localhost:8001/ui/`) returns a 200 OK status.
        *   `- [ ]` The response for the base UI route contains the content from `templates/base.html`.
        *   `- [ ]` The HTML response includes `<script>` tags referencing HTMX and Alpine.js CDNs.
        *   `- [ ]` A basic integration test passes, confirming the route is reachable and renders the base template.
    *   **Status:** To Do

---

## Feature Area: Dashboard / Basic View (UC3)

*   **US-05.1: Display Recent Events on Dashboard**
    *   **As an** Analyst,
    *   **I want** to load the main UI page (`/ui/`) and see a list of the 10 most recent events (displaying timestamp, ID, and a snippet of content/metadata),
    *   **So that** I can get a quick overview of the latest memory activity.
    *   **Tasks:**
        *   `- [ ]` Create a `/ui/` route in `routes/ui/base.py`.
        *   `- [ ]` Implement logic in the route to fetch the latest N events (e.g., using `EventRepository`).
        *   `- [ ]` Create `templates/dashboard.html` (or similar) that extends `base.html`.
        *   `- [ ]` Add logic in `dashboard.html` to iterate over events and display required fields.
        *   `- [ ]` Pass events data from the route to the template context.
    *   **Acceptance Criteria:**
        *   `- [ ]` Accessing `/ui/` loads the `dashboard.html` template.
        *   `- [ ]` The page displays a list containing the N most recent events from the database.
        *   `- [ ]` Each list item shows at least the event timestamp, ID, and a readable snippet of its content/metadata.
        *   `- [ ]` If no events exist, a clear message is displayed.
    *   **Status:** To Do

*   **US-05.2: Paginate/Load More Events on Dashboard**
    *   **As a** Developer,
    *   **I want** the main event list on the dashboard to have a "Load More" button (or simple pagination links) that uses HTMX,
    *   **So that** I can browse beyond the initial view without a full page reload.
    *   **Tasks:**
        *   `- [ ]` Add a "Load More" button/link to `dashboard.html`.
        *   `- [ ]` Add HTMX attributes (`hx-get`, `hx-target`, `hx-swap`) to the button/link.
        *   `- [ ]` Create a new route (e.g., `/ui/events-partial`) that accepts pagination parameters (e.g., offset/page).
        *   `- [ ]` Implement logic in the new route to fetch the *next* N events.
        *   `- [ ]` Create a partial template (`templates/partials/event_list.html`?) to render just the list of events.
        *   `- [ ]` The new route should render the partial template.
    *   **Acceptance Criteria:**
        *   `- [ ]` A "Load More" button or pagination links are visible on the dashboard if more events exist.
        *   `- [ ]` Clicking the button/link triggers an HTMX GET request to a specific partial-rendering endpoint.
        *   `- [ ]` The request includes necessary parameters (e.g., current offset or next page number).
        *   `- [ ]` The endpoint returns an HTML fragment containing the next set of events.
        *   `- [ ]` The event list on the dashboard is updated (e.g., appended or replaced) with the new events without a full page refresh.
    *   **Status:** To Do

*   **US-05.3: Visually Distinguish Event Types**
    *   **As an** Analyst,
    *   **I want** basic visual distinction between different `event_type` (or similar metadata) entries in the list,
    *   **So that** I can quickly scan for specific types of events.
    *   **Tasks:**
        *   `- [ ]` Define CSS classes corresponding to different event types in `static/css/style.css`.
        *   `- [ ]` Modify the event list rendering (in `dashboard.html` and/or `partials/event_list.html`) to add the appropriate CSS class based on event metadata.
    *   **Acceptance Criteria:**
        *   `- [ ]` Events with different `event_type` metadata have visually distinct styles (e.g., background color, border, icon).
        *   `- [ ]` The correct CSS class is applied dynamically based on the data of each event.
    *   **Status:** To Do

---

## Feature Area: Search & Filtering (UC2 & UC3)

*   **US-05.4: Create Dedicated Search Page**
    *   **As a** Developer,
    *   **I want** a dedicated Search page (`/ui/search`) accessible from the main navigation,
    *   **So that** I have a focused area for querying the memory.
    *   **Tasks:**
        *   `- [ ]` Add a link to `/ui/search` in the navigation within `templates/base.html`.
        *   `- [ ]` Create a `/ui/search` route in `routes/ui/base.py`.
        *   `- [ ]` Create `templates/search.html` that extends `base.html`.
        *   `- [ ]` Add basic form elements (inputs, submit button) to `search.html`.
        *   `- [ ]` The route should render `search.html`.
    *   **Acceptance Criteria:**
        *   `- [ ]` The "Search" link in the main navigation points to `/ui/search`.
        *   `- [ ]` Accessing `/ui/search` returns 200 OK and renders the `search.html` template.
        *   `- [ ]` The search page contains input fields for filtering and a submit button.
    *   **Status:** To Do

*   **US-05.5: Filter Events by Date Range**
    *   **As an** Analyst,
    *   **I want** input fields on the Search page to filter events by a **date range** (start/end date),
    *   **So that** I can isolate events within a specific timeframe.
    *   **Tasks:**
        *   `- [ ]` Add date input fields (e.g., `<input type="date">`) to the form in `search.html`.
        *   `- [ ]` Modify the search results route (or create one) to accept `ts_start` and `ts_end` query parameters.
        *   `- [ ]` Update the database query logic to include the timestamp range filter.
        *   `- [ ]` Ensure the search form submits these parameters (likely via HTMX GET).
        *   `- [ ]` (Optional) Enhance date inputs with an Alpine.js-based date picker if native ones are insufficient.
    *   **Acceptance Criteria:**
        *   `- [ ]` Date range input fields are present on the search form.
        *   `- [ ]` Submitting the form sends the selected dates as query parameters.
        *   `- [ ]` The search results displayed reflect only events within the specified date range (inclusive).
    *   **Status:** To Do

*   **US-05.6: Filter Events by Metadata**
    *   **As an** Analyst,
    *   **I want** an input field(s) on the Search page to filter events by **metadata**,
    *   **So that** I can find events based on specific tags or attributes.
    *   **Tasks:**
        *   `- [ ]` Add input field(s) for metadata filtering (e.g., a single JSON input, or dynamic key/value pairs) to `search.html`.
        *   `- [ ]` Modify the search results route to accept metadata filter parameters.
        *   `- [ ]` Update the database query logic to use JSONB operators (e.g., `@>`) for filtering.
        *   `- [ ]` Ensure the search form submits these parameters (likely via HTMX GET).
        *   `- [ ]` (Optional) Use Alpine.js to allow users to easily add/remove multiple key-value metadata filters in the UI.
    *   **Acceptance Criteria:**
        *   `- [ ]` Metadata filter input(s) are present on the search form.
        *   `- [ ]` Submitting the form sends the metadata filter criteria as query parameters.
        *   `- [ ]` The search results displayed reflect only events matching the specified metadata filters.
    *   **Status:** To Do

*   **US-05.7: Perform Similarity Search**
    *   **As an** Analyst,
    *   **I want** a text input field on the Search page to perform a **similarity search** based on content,
    *   **So that** I can find memories semantically related to my query text.
    *   **Tasks:**
        *   `- [ ]` Add a text input field for the similarity query to `search.html`.
        *   `- [ ]` Modify the search results route to accept a `query_text` parameter.
        *   `- [ ]` Implement logic in the route to:
            *   `- [ ]` Generate an embedding for the `query_text` (using `EmbeddingService`).
            *   `- [ ]` Perform a vector search in the database using the generated embedding (e.g., via `EventRepository.search_by_embedding`).
        *   `- [ ]` Ensure the search form submits this query text (likely via HTMX GET).
    *   **Acceptance Criteria:**
        *   `- [ ]` A text input for similarity search is present on the search form.
        *   `- [ ]` Submitting the form with text triggers a vector search.
        *   `- [ ]` The search results are ordered based on vector similarity to the query text.
        *   `- [ ]` Similarity scores are potentially displayed with the results.
    *   **Status:** To Do

*   **US-05.8: Update Search Results Dynamically**
    *   **As a** Developer,
    *   **I want** the search results area to be updated via HTMX after submitting a search query,
    *   **So that** the search feels interactive.
    *   **Tasks:**
        *   `- [ ]` Define a target element (e.g., `<div id="search-results">`) in `search.html`.
        *   `- [ ]` Configure the search form in `search.html` with HTMX attributes (`hx-get` pointing to the results route, `hx-target="#search-results"`, `hx-swap`).
        *   `- [ ]` Ensure the search results route renders a partial template containing only the results list.
    *   **Acceptance Criteria:**
        *   `- [ ]` Submitting the search form triggers an HTMX request.
        *   `- [ ]` Only the designated search results area of the page is updated with the response.
        *   `- [ ]` The rest of the page (navigation, search form itself) remains unchanged (no full page reload).
    *   **Status:** To Do

*   **US-05.9: Display Active Filters**
    *   **As an** Analyst,
    *   **I want** active filters (date range, metadata) to be clearly displayed above or near the search results,
    *   **So that** I know what criteria are currently applied.
    *   **Tasks:**
        *   `- [ ]` Modify the search results route/template to include information about the active filters used for the query.
        *   `- [ ]` Display these active filters in the results partial template.
        *   `- [ ]` (Optional) Use Alpine.js to dynamically update the display of filter inputs themselves based on the submitted values, providing immediate feedback.
    *   **Acceptance Criteria:**
        *   `- [ ]` When a search is performed with active filters (date, metadata), these filters are clearly displayed along with the results.
        *   `- [ ]` If no filters are active, this is also clear (e.g., no filter display area shown).
    *   **Status:** To Do

---

## Feature Area: Event Detail View (UC3)

*   **US-05.10: Load Event Details Dynamically**
    *   **As an** Analyst,
    *   **I want** to click on an event's ID or summary in any list (dashboard, search results) and see its full details loaded dynamically,
    *   **So that** I can examine a specific memory without leaving the current context entirely.
    *   **Tasks:**
        *   `- [ ]` Make event IDs/summaries clickable links/buttons in list templates.
        *   `- [ ]` Add HTMX attributes (`hx-get`, `hx-target`, `hx-swap`) to these elements, pointing to a detail route (e.g., `/ui/events/{event_id}`).
        *   `- [ ]` Define a target element for the detail view (e.g., a modal `div`, or a dedicated section on the page).
        *   `- [ ]` Create the `/ui/events/{event_id}` route.
        *   `- [ ]` Implement logic in the route to fetch the specific event by ID.
        *   `- [ ]` Create a partial template (`templates/partials/event_detail.html`?) to render the details.
        *   `- [ ]` The detail route should render the partial template.
    *   **Acceptance Criteria:**
        *   `- [ ]` Clicking an event in a list triggers an HTMX request to a detail endpoint.
        *   `- [ ]` The endpoint returns an HTML fragment with the event's details.
        *   `- [ ]` A designated area on the page (or a modal) is updated with this fragment.
        *   `- [ ]` The detail view shows information specific to the clicked event.
    *   **Status:** To Do

*   **US-05.11: Display Raw Event Data**
    *   **As a** Developer,
    *   **I want** the event detail view to clearly display the full `content` and `metadata` JSON objects in a readable format,
    *   **So that** I can easily inspect the raw data.
    *   **Tasks:**
        *   `- [ ]` Modify the `event_detail.html` partial template.
        *   `- [ ]` Use `<pre>` tags or similar to display the `content` and `metadata` JSON.
        *   `- [ ]` Potentially use a Jinja filter or helper function for pretty-printing the JSON.
    *   **Acceptance Criteria:**
        *   `- [ ]` The event detail view renders the `content` JSON in a formatted, readable block.
        *   `- [ ]` The event detail view renders the `metadata` JSON in a formatted, readable block.
    *   **Status:** To Do

*   **US-05.12: Show Linked Events (Stretch Goal)**
    *   **As an** Analyst,
    *   **I want** the event detail view to show lists of directly linked events (incoming/outgoing edges, max 1-hop),
    *   **So that** I can see immediate relationships.
    *   **Tasks:**
        *   `- [ ]` Implement repository methods to find related nodes/events via the `edges` table for a given `node_id` (1-hop).
        *   `- [ ]` Modify the detail route (`/ui/events/{event_id}`) to fetch these related events.
        *   `- [ ]` Pass the related events data to the `event_detail.html` partial template.
        *   `- [ ]` Add sections to the template to display lists of "Linked From" and "Links To" events.
    *   **Acceptance Criteria:**
        *   `- [ ]` The event detail view includes sections for related events.
        *   `- [ ]` These sections list events linked via the `edges` table (source or target matches the current event ID).
        *   `- [ ]` If no linked events exist, the sections indicate this clearly.
    *   **Status:** To Do

---

## Feature Area: Basic Ingestion (UC1 - for Testing) (Lower Priority)

*   **US-05.13: Provide Simple Event Ingestion Form**
    *   **As a** Tester,
    *   **I want** a simple form where I can paste JSON for `content` and `metadata` and submit it to create a new event via HTMX,
    *   **So that** I can quickly add test data through the UI.
    *   **Tasks:**
        *   `- [ ]` Create a new route/template for the ingestion form (e.g., `/ui/ingest`).
        *   `- [ ]` Add text areas for `content` and `metadata` JSON input.
        *   `- [ ]` Add HTMX attributes (`hx-post` pointing to the API's `/v1/events` endpoint, `hx-target` for feedback).
        *   `- [ ]` Define a target element to display success/error messages.
        *   `- [ ]` Potentially use Alpine.js for basic client-side JSON validation before submission.
    *   **Acceptance Criteria:**
        *   `- [ ]` An ingestion form page/section is accessible.
        *   `- [ ]` The form allows inputting JSON for `content` and `metadata`.
        *   `- [ ]` Submitting the form triggers an HTMX POST request to the `/v1/events` API endpoint.
        *   `- [ ]` The request body contains the JSON data entered by the user.
        *   `- [ ]` A success message is displayed in a target area upon successful creation (201 status).
        *   `- [ ]` An error message is displayed if the API returns an error (e.g., 422, 500).
    *   **Status:** To Do

--- 