to get repo files path
find . \
  -not -path "*/node_modules/*" \
  -not -path "*/.git/*" \
  -not -path "*/dist/*" \
  -not -path "*/build/*" \
  -not -path "*/harness/chakra/*" \
-not -path "*/.venv/*" \
  | sort > repo_tree.txt
