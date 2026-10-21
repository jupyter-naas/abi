# Templates are Jinja, not Python: their test files (remote_module/package/tests)
# only run once rendered into a module. Copier copies the template folders
# below this one, never this file.
collect_ignore_glob = ["*"]
