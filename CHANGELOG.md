# CHANGELOG


## v0.3.0 (2026-06-04)

### Features

- Log release version at startup
  ([`3e42a60`](https://github.com/johannrichard/caldav-automata/commit/3e42a60129c708666d6af684cd3e5e6e21a903ff))

- Merge pull request #10 from johannrichard/copilot/log-release-version-on-startup
  ([`0477ead`](https://github.com/johannrichard/caldav-automata/commit/0477ead1a39db11b7d7ca87d8b222a36df22bd00))

feat: log release version at startup


## v0.2.0 (2026-06-04)

### Continuous Integration

- Trigger docker publish on release.published
  ([`11457c5`](https://github.com/johannrichard/caldav-automata/commit/11457c58a9781ae6774bea5e23102c1119a68482))


## v0.1.0 (2026-06-03)

### Bug Fixes

- Adjust .gitignore
  ([`8ff47ff`](https://github.com/johannrichard/caldav-automata/commit/8ff47ff6ff4a7c60bb3ebba66816ef473bcacaf6))

- Use dict[str, Any] type annotation for client_kwargs
  ([`f4e569b`](https://github.com/johannrichard/caldav-automata/commit/f4e569b52e8a2894272a8f3d00492e2aef1ea131))

### Chores

- :construction: add merged-master publish trigger logic
  ([`db4871f`](https://github.com/johannrichard/caldav-automata/commit/db4871f129088bb8cdf7ef6124461fc9a2817bfa))

- :label: tighten semver validation and retention docs sync
  ([`9e719a2`](https://github.com/johannrichard/caldav-automata/commit/9e719a258079acf10701fe577cca41e3606436bc))

- :recycle: harden ghcr cleanup workflow configuration
  ([`df4b4fd`](https://github.com/johannrichard/caldav-automata/commit/df4b4fd21a6cd2743071160958a08e318f1aeca6))

- :rocket: switch release tagging to semantic-release
  ([`36203a0`](https://github.com/johannrichard/caldav-automata/commit/36203a01e7c5b61c07a9a22788da9542445f4af6))

- :whale: add semver docker publishing and ghcr cleanup
  ([`227b224`](https://github.com/johannrichard/caldav-automata/commit/227b224e8b2740e4197a23a5702fe2408a97364b))

### Continuous Integration

- :bug: fix build – publish on `main`
  ([`8a7d53c`](https://github.com/johannrichard/caldav-automata/commit/8a7d53c53bfb81e004d688d1bd23cd4807644f7f))

we were publishing on `master` - it should be `main`

### Documentation

- Replace placeholder clone URL with generic form
  ([`7aaf86a`](https://github.com/johannrichard/caldav-automata/commit/7aaf86a541bad3821936ecfde5f1d52d0771fedd))

### Features

- Add .env.example and update docker-compose to use env_file
  ([`8dbb58c`](https://github.com/johannrichard/caldav-automata/commit/8dbb58cbaf4de4afc9a72b71a8a9840ffd2a4689))

- Add subject/note conditions to LISP rule engine
  ([`d6e6840`](https://github.com/johannrichard/caldav-automata/commit/d6e68400f4fcef1e26c1a2b15f3b2aadb32b21ef))

- Initial CalDAV Automata implementation
  ([`df26774`](https://github.com/johannrichard/caldav-automata/commit/df267748873bbdae62b3a2833ab7d330b1ed7d26))

- Radicale CalDAV backend + FastAPI proxy in a single Docker container - LISP rule engine:
  S-expression parser, rule compiler, action dispatcher - Actions: add-attendee (idempotent),
  set-alert (idempotent VALARM) - Rules hot-reloaded from /rules/**/*.lisp on every event write -
  Docker Compose ready; works with Apple Calendar (iOS/macOS) - Full README with quick-start, rule
  examples, auth configuration

- Support per-account DAVClient knobs for iCloud CalDAV connections
  ([`50abe8d`](https://github.com/johannrichard/caldav-automata/commit/50abe8d7e44cb671b3de3a9397f9abe788050b8e))

- Extend _poll_account() to pass optional ssl_verify_cert, auth_type, and headers from the account
  config to caldav.DAVClient, matching the pattern recommended by the python-caldav
  icloud_example.py. - The generic base URL (https://caldav.icloud.com/) is retained and the caldav
  library's principal() performs PROPFIND-based URL discovery automatically, just as the referenced
  example did manually. - Update config/calendar.example.yaml with iCloud-specific comments and the
  new optional per-account keys. - Update README.md to explain iCloud URL discovery and document the
  new ssl_verify_cert, auth_type, and headers account fields.
