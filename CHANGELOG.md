# [1.2] - 2025-07-01

### Added
- Parallel Processing for faster scraping
- Refactored scraping logic using mixins and a conductor design to separate concerns and simplify horizontal expansion.
- WebSocket support via Daphne (server running, pending view/task integration)
- Python script to watch django-background-tasks and pause extracting to scrape a site
- Custom exceptions for connection failures, timeouts, and item and link errors
- Static Selenium connection method for reusable driver initialization
- Loggers with script names and line numbers for debugging
- Dashboard with statistics, recent jobs, and quick actions

### Changed
- Complete redesign of UI
- Item previews are no longer showing automatically (prevents rate-limiting)

### Fixed
- Update button on index page

# [1.1] - 2025-09-28

### Added
- New items page UI
- Toggle saved items
- Toggle item previews
- View images and videos in a bigger ratio
- Scraped links site filters
- Child link scrape time recorded
- Auto update when visting items page in settings
- Rules for scraping

### Changed
- Clicking item row selects item

### Fixed
- Made Selenium run as a fallback if requests can't decode characters

# [1.0] - 2025-08-11
- Initial Release
- Custom user agents
- Custom headers
- Django-background-tasks
- Added a Python script for concurrent background task execution
- txt with scrape info