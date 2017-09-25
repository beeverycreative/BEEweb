#!/usr/bin/env bash

# Portuguese language
msgfmt translations/pt/LC_MESSAGES/messages.po --output-file translations/pt/LC_MESSAGES/messages.mo
msgfmt src/octoprint/translations/pt/LC_MESSAGES/messages.po --output-file src/octoprint/translations/pt/LC_MESSAGES/messages.mo

# German language
msgfmt translations/de/LC_MESSAGES/messages.po --output-file translations/de/LC_MESSAGES/messages.mo
msgfmt src/octoprint/translations/de/LC_MESSAGES/messages.po --output-file src/octoprint/translations/de/LC_MESSAGES/messages.mo
