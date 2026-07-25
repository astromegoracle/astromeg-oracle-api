# Private Oracle knowledge

The Astromeg knowledge files are private and must not be committed to this
repository. The application loads a generated JSON corpus from the first
available location:

1. `ORACLE_KNOWLEDGE_FILE`
2. `/etc/secrets/astromeg_oracle_knowledge.json`
3. `private/astromeg_oracle_knowledge.json`

Build the corpus locally:

```sh
python3 -m pip install -r scripts/requirements-knowledge.txt
python3 scripts/build_oracle_knowledge.py \
  --input-zip "/path/to/ASTROMEG_KNOWLEDGE_DATASETS.zip" \
  --output "private/astromeg_oracle_knowledge.json"
```

For Render, upload the generated file as a secret file named
`astromeg_oracle_knowledge.json`. Render mounts it at `/etc/secrets/`, which
the application discovers automatically. Redeploy the service after replacing
the file.

Only relevant chunks are added to `/oracle/chat` requests. The calculator
routes and the Custom GPT OpenAPI schema do not receive this private context.
