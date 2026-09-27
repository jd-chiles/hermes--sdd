# Profile recipes

The plugin's role names are `coordinator`, `architect`, `engineer`, `reviewer`, `qa`, and `writer`. On an executing request the native bridge provisions missing names through `hermes profile create` and enables the installed plugin in each profile. Hermes owns profile storage and worker lifecycle; this package never edits user profile files directly. Existing profiles are preserved and reused.
