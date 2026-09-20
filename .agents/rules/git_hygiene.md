# Git Hygiene & Personal Reference Privacy Rule

Whenever creating or modifying documentation or scratch materials:
1. **Identify Personal / Internal Reference Files**: Any documents containing internal review prep, presentation scripts, budget/cost calculations, business plans, personal notes, or proprietary strategy must NOT be exposed to public git repositories.
2. **Automatically Update `.gitignore`**: Whenever creating a personal reference, review document, or financial/strategy note, verify that `.gitignore` contains the rule to exclude it from git tracking.
3. **Preserve Local Copies**: Never delete these files from the user's workspace; keep them available locally for the user while guaranteeing they will not be committed or pushed to GitHub.
