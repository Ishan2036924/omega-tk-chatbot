# Git commands – run one at a time

**Set your identity (do once):**
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

**If you just finished the commit in the editor**, push the new commit:
```bash
cd /Users/nmoursi/omega-tk-chatbot
git push origin feature/streamlit-ui
```

**To fix author on the last commit** (optional):
```bash
git commit --amend --reset-author --no-edit
git push origin feature/streamlit-ui
```

**Note:** Don’t paste whole blocks with `#` comments into the terminal. Run each command on its own line; lines starting with `#` are comments for humans, and zsh can misinterpret them.
