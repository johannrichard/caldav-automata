# CHANGELOG


## v0.12.2 (2026-06-16)

### Build System

- :package: include example assets via setuptools data-files
  ([`14cd393`](https://github.com/johannrichard/caldav-automata/commit/14cd3931c27d3d0b0d2caf320924da218dd4ecd8))

- 🩹 fix pyproject
  ([`f51cc7f`](https://github.com/johannrichard/caldav-automata/commit/f51cc7f80c6f88c5c86ec3d43ae018738cbcc466))


## v0.12.1 (2026-06-16)

### Bug Fixes

- :bug: support ICS alias names in logs and rules
  ([`34c471f`](https://github.com/johannrichard/caldav-automata/commit/34c471f9045da85fb23745453a7d04fd10735435))

### Documentation

- :memo: clarify ICS alias matching behavior
  ([`89f64a0`](https://github.com/johannrichard/caldav-automata/commit/89f64a030d43e78cbacccfaec0f5434cc558b90a))

- :memo: generalize provider password examples
  ([`bbb67e2`](https://github.com/johannrichard/caldav-automata/commit/bbb67e23171c03c491543fede092fa2c31234424))

- :memo: keep organizer format unchanged
  ([`fe9241a`](https://github.com/johannrichard/caldav-automata/commit/fe9241a3b21d18afb5968d8ef4db752ae751d06a))

### Refactoring

- :art: tidy ICS alias handling
  ([`b7361cb`](https://github.com/johannrichard/caldav-automata/commit/b7361cb4546ea0d5c379ab1013e7976894d57d10))

- :label: improve ICS alias naming clarity
  ([`b87ca63`](https://github.com/johannrichard/caldav-automata/commit/b87ca63821f86a76de98d8cea094c1cdf2b27bc4))

- :lipstick: polish ICS alias log formatting
  ([`e1785ba`](https://github.com/johannrichard/caldav-automata/commit/e1785ba078fbfeea8646b53ce0d3548e21e3366e))

- :recycle: clarify ICS alias normalization
  ([`89fac61`](https://github.com/johannrichard/caldav-automata/commit/89fac6192420bb445af029d386f5d46cc0d4eb41))


## v0.12.0 (2026-06-16)

### Bug Fixes

- :bug: fix User-Agent casing and log message capitalization
  ([`a77e424`](https://github.com/johannrichard/caldav-automata/commit/a77e42452ce10aec27becd9d5c78967c408360a9))

### Features

- :sparkles: add ICS feed support for read-only calendar polling
  ([`e0a014d`](https://github.com/johannrichard/caldav-automata/commit/e0a014d5c4a6486db80e0cab3778a8033bd30637))


## v0.11.0 (2026-06-16)

### Bug Fixes

- :bug: handle None calendar names in available-calendars log
  ([`1e7440a`](https://github.com/johannrichard/caldav-automata/commit/1e7440ae44797fb6b80277195839a42992d8a8c9))

- :warning: warn when copy-to-calendar skips idempotency due to missing UID
  ([`bf64725`](https://github.com/johannrichard/caldav-automata/commit/bf647251c5476eb9d52a008caab7f3eb56618be8))

### Documentation

- :memo: document copy-to-calendar action in README with examples
  ([`a54c635`](https://github.com/johannrichard/caldav-automata/commit/a54c635980f701fd6f9bccfdf35791547278d967))

- :pencil: add copy-to-calendar example and docs to example.lisp.example
  ([`4904b41`](https://github.com/johannrichard/caldav-automata/commit/4904b41d27481f50f0a764f957f242a9bdb6291a))

### Features

- :sparkles: add copy-to-calendar action with UID-based idempotency
  ([`4bef34b`](https://github.com/johannrichard/caldav-automata/commit/4bef34b1da5523da54cdccfc4400e9ab34b3ef5f))

- :sparkles: log available calendars on account connect
  ([`4908843`](https://github.com/johannrichard/caldav-automata/commit/4908843b860ee1d4c2b565ff2a92fe9782b0b53e))

- :zap: thread calendar_getter through rule dispatch chain for copy-to-calendar
  ([`16543f8`](https://github.com/johannrichard/caldav-automata/commit/16543f8d3f663911a2dfc0ce72d808f38347b0df))


## v0.10.3 (2026-06-13)

### Build System

- 📦 include config, rules, and deploy files in package
  ([`5b092d4`](https://github.com/johannrichard/caldav-automata/commit/5b092d48e5f1981dde47233288edaec8ad7eee7c))

### Chores

- 🔧 update systemd credential storage path to /var/caldav-automata
  ([`5141346`](https://github.com/johannrichard/caldav-automata/commit/51413462b0784497aa5144655bcb1990545854c3))

### Documentation

- 📚 add pip install instructions and improve systemd credential setup
  ([`dc8449a`](https://github.com/johannrichard/caldav-automata/commit/dc8449ac9987369c3fea99c4c7bbc503f2b6c05c))


## v0.10.2 (2026-06-06)

### Bug Fixes

- :bug: use installed package version at startup
  ([`897bc90`](https://github.com/johannrichard/caldav-automata/commit/897bc90163b42f2d979c1fb2d95f49c4d5a3c8b6))


## v0.10.1 (2026-06-06)

### Bug Fixes

- :bug: make systemd stop terminate cleanly
  ([`d02a8d4`](https://github.com/johannrichard/caldav-automata/commit/d02a8d4d09605aa4fd1f1d6fecd28315deebe4e6))

### Chores

- :mag: log resolved sqlite state db path
  ([`1dea62e`](https://github.com/johannrichard/caldav-automata/commit/1dea62e3cc4235ce6a3c783758d5e47b51ffb83a))


## v0.10.0 (2026-06-06)

### Continuous Integration

- :recycle: keep 15 docker image versions
  ([`aa529b5`](https://github.com/johannrichard/caldav-automata/commit/aa529b5bf6066e7339eed8ab55489865501382be))

### Documentation

- :memo: clarify systemd /opt installation requirement
  ([`745a618`](https://github.com/johannrichard/caldav-automata/commit/745a61820f9b0d04cf661f95b4d2e2ef6c1be270))

### Features

- :lock: integrate systemd-creds for iCloud password
  ([`8d2eb46`](https://github.com/johannrichard/caldav-automata/commit/8d2eb46e9891f09fabb5ae26cd256f6fa4931dc8))


## v0.9.4 (2026-06-06)

### Build System

- :construction_worker: add installable package metadata and CLI
  ([`f7dd75c`](https://github.com/johannrichard/caldav-automata/commit/f7dd75c6c847bca4fa41fa4c2dd7246f04fe3c3c))

### Documentation

- :memo: add systemd deployment and host install guide
  ([`1363337`](https://github.com/johannrichard/caldav-automata/commit/13633376eb089de300d881ad8ad9b949d5138fbc))


## v0.9.3 (2026-06-06)

### Performance Improvements

- :zap: cache principal organizer discovery per account
  ([`4fcb916`](https://github.com/johannrichard/caldav-automata/commit/4fcb916850e17924716b3dc153a470794b196442))


## v0.9.2 (2026-06-06)

### Bug Fixes

- :bug: derive organizer from principal for attendee adds
  ([`5b06499`](https://github.com/johannrichard/caldav-automata/commit/5b0649928ddf8012fb947c2fd120c63055935b1a))

### Documentation

- :memo: clarify organizer fallback-only config
  ([`4f34d52`](https://github.com/johannrichard/caldav-automata/commit/4f34d52e41ff58435e5eb21f5ef9a41989ddaf73))


## v0.9.1 (2026-06-06)

### Bug Fixes

- :bug: set organizer only when missing after attendee actions
  ([`ab63196`](https://github.com/johannrichard/caldav-automata/commit/ab631966ea67b9a07aa89cdeb2cdacf4c8185dea))

### Documentation

- :memo: clarify organizer default behavior
  ([`4a15668`](https://github.com/johannrichard/caldav-automata/commit/4a15668f500766c4d922ecb611b60a2c547f428c))


## v0.9.0 (2026-06-06)

### Documentation

- :memo: document account-level organizer config
  ([`be5c9a6`](https://github.com/johannrichard/caldav-automata/commit/be5c9a6c57e9637ecf6d90fd0f710e66c27ee8ec))

### Features

- :sparkles: enforce account organizer for attended events
  ([`708d0d9`](https://github.com/johannrichard/caldav-automata/commit/708d0d9fc73b74377fe950e2e25bdb1a9f4aebdd))


## v0.8.0 (2026-06-06)

### Bug Fixes

- :bug: abort on second ctrl-c
  ([`75092ad`](https://github.com/johannrichard/caldav-automata/commit/75092ad08189b6f6e53cddd4365fabb34db808a1))

- :bug: align RFC6638 scheduling invite handling
  ([`afa7772`](https://github.com/johannrichard/caldav-automata/commit/afa7772a04b884d8ae48f042215e41a2fd27dfe6))

- :bug: flush event state after each event
  ([`eb70944`](https://github.com/johannrichard/caldav-automata/commit/eb709446bbaf8893c402c2c6d83561b0bf006a51))

- :bug: handle delta sync events without payload
  ([`3c2dda2`](https://github.com/johannrichard/caldav-automata/commit/3c2dda2a3bcb07a08a7b9c8eeaacf02023a720b0))

- 🐛 pass ical string to calendar.add_event instead of object
  ([`63313cb`](https://github.com/johannrichard/caldav-automata/commit/63313cb603fa9f076cc95d7ca462cb302312282b))

### Chores

- :wrench: add VS Code Python debug config
  ([`eea4058`](https://github.com/johannrichard/caldav-automata/commit/eea40586528c872639f2be816f1870d9d7443865))

- :wrench: update launch logging env
  ([`18cf867`](https://github.com/johannrichard/caldav-automata/commit/18cf867007aa92b948a24cefce8db6ea567c25be))

- 🙈 ignore .DS_Store files
  ([`59666d6`](https://github.com/johannrichard/caldav-automata/commit/59666d67b3d99fa7e2b9813fae594392f4b6a614))

### Documentation

- :memo: clarify add-attendee scheduling options
  ([`4a8b290`](https://github.com/johannrichard/caldav-automata/commit/4a8b2901b322d0492da2de68aea0ad52efb5517a))

- :memo: document log color environment settings
  ([`991c872`](https://github.com/johannrichard/caldav-automata/commit/991c872f049ed1982913f8c2b2cbaaadb52439e4))

- :memo: explain add-attendee option values
  ([`3fdbc5b`](https://github.com/johannrichard/caldav-automata/commit/3fdbc5b0dc49a6f3c548e800af4a7c85b0e4cab4))

- :memo: fix README markdownlint violations
  ([`f009a34`](https://github.com/johannrichard/caldav-automata/commit/f009a34ef18962e1dc0dc394b4fc0fd45cb56fee))

- 📝 update config and docs for SQLite state storage
  ([`aff220b`](https://github.com/johannrichard/caldav-automata/commit/aff220b0746c93ce635c6cbf7ecea7e47c3342a6))

### Features

- :sparkles: add configurable colored logging
  ([`5b86ba0`](https://github.com/johannrichard/caldav-automata/commit/5b86ba098a8b3de61f94963e881fe9ab0542ab49))

- ⚠️ warn when rules reload after disk changes
  ([`e30cf54`](https://github.com/johannrichard/caldav-automata/commit/e30cf548de11699f5e24d627040fa77aae5775b2))

### Refactoring

- ♻️ replace JSON state file with SQLite-backed state DB
  ([`a30339e`](https://github.com/johannrichard/caldav-automata/commit/a30339e6e7bdcfcdb5db511f7573d3034c3a2c2d))


## v0.7.0 (2026-06-06)

### Build System

- 🐳 upgrade Python base image to 3.13
  ([`1a3b224`](https://github.com/johannrichard/caldav-automata/commit/1a3b22492a92d8181d3af23534d7eb828bdeb3ce))

### Chores

- 🔧 add Black formatter configuration and CI
  ([`4cb37a8`](https://github.com/johannrichard/caldav-automata/commit/4cb37a8394b8b9ecd20a8f920bd189fc000902c4))

### Code Style

- :art: format code with black
  ([`5e27b47`](https://github.com/johannrichard/caldav-automata/commit/5e27b478ad23e9c9714727139ba08b9f8fdc49c9))

- 🎨 apply Black formatting to Python files
  ([`4c5b426`](https://github.com/johannrichard/caldav-automata/commit/4c5b426f2e99ad50a2e9bcbdd8a0f0f6d016139e))

### Features

- ✨ add sync-token state tracking and fix event persistence
  ([`df8e0c8`](https://github.com/johannrichard/caldav-automata/commit/df8e0c8127c1db0c02a159db37514a70dac833d4))


## v0.6.0 (2026-06-05)

### Bug Fixes

- ✅ default SERVER schedule agent
  ([`a9028ec`](https://github.com/johannrichard/caldav-automata/commit/a9028ecc6bb940027344309aa5c0f9d4fe30ad42))

- 🤖 set SERVER as default schedule agent
  ([`39e2c47`](https://github.com/johannrichard/caldav-automata/commit/39e2c47fb23d0028c45a776f8baacc2e61c464cf))

### Features

- 🧭 add organizer rule filter support
  ([`37bcd8f`](https://github.com/johannrichard/caldav-automata/commit/37bcd8ff8d673e34b26ebe6ee1ea8211d3c04be6))


## v0.5.2 (2026-06-04)

### Build System

- :construction: release on build commits
  ([`de7af52`](https://github.com/johannrichard/caldav-automata/commit/de7af52a93c2229400e83225a5ad02280cbf57cb))

- 🏗️ `linux/arm/v7` version
  ([`e048faa`](https://github.com/johannrichard/caldav-automata/commit/e048faad9a08defb442396401189569621f36c58))

Build an `ARM/v7` version too


## v0.5.1 (2026-06-04)

### Bug Fixes

- :patch: README.mda
  ([`b091722`](https://github.com/johannrichard/caldav-automata/commit/b091722433d0aea2f6958e7fb0da3b4fdb8e3dd4))


## v0.5.0 (2026-06-04)

### Continuous Integration

- :hammer: tighten gitmoji validation
  ([`aee903b`](https://github.com/johannrichard/caldav-automata/commit/aee903b9598c6b07cb50ac6a81c49aedddc647df))

- :recycle: prepare for Railway
  ([`2471bcd`](https://github.com/johannrichard/caldav-automata/commit/2471bcd7e29b2c373fdf23cc70b6eb4b411716e8))

- :white_check_mark: enforce commit message format
  ([`8c43580`](https://github.com/johannrichard/caldav-automata/commit/8c43580a5096b0751920c3612848dd1738f4815e))


## v0.4.0 (2026-06-04)

### Features

- 🚀 Gate Docker publish on semantic-release release creation
  ([`4e6a02e`](https://github.com/johannrichard/caldav-automata/commit/4e6a02ef7339220413a6469ef0e0f88a6ca96784))

Gate Docker publish on semantic-release release creation


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
