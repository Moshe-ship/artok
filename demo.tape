# artok demo - Arabic Token Tax Calculator
# Run: vhs demo.tape

Output demo.gif
Set Shell "zsh"
Set FontSize 13
Set Width 1200
Set Height 700
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms
Set Padding 16

# Activate venv
Hide
Type "source .venv/bin/activate && clear"
Enter
Sleep 500ms
Show

# --- Scene 1: Basic — the tax is real ---
Sleep 300ms
Type 'artok "الذكاء الاصطناعي يغير العالم" -e "AI is changing the world" -t gpt4.1,claude-sonnet,qwen3.5,deepseek,mistral-small'
Sleep 400ms
Enter
Sleep 5s

# --- Scene 2: Benchmark ---
Type 'artok --benchmark -t gpt4.1,claude-sonnet,qwen3.5,deepseek,mistral-small,llama4'
Sleep 400ms
Enter
Sleep 6s

# --- Scene 3: Tashkeel ---
Type 'artok "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ" --tashkeel -t gpt4.1,claude-sonnet,qwen3.5'
Sleep 400ms
Enter
Sleep 5s

# --- Scene 4: Heatmap ---
Type 'artok "الذكاء الاصطناعي يغير حياتنا بشكل جذري ومستمر" --heatmap -t gpt4.1'
Sleep 400ms
Enter
Sleep 4s

# --- Scene 5: Dialects ---
Type 'artok --dialects -t gpt4.1,claude-sonnet,qwen3.5,deepseek'
Sleep 400ms
Enter
Sleep 5s

# --- Scene 6: Leaderboard ---
Type 'artok "الذكاء الاصطناعي يغير العالم" --leaderboard -t gpt4.1,gpt4.1-nano,claude-sonnet,claude-haiku,qwen3.5,deepseek,mistral-small'
Sleep 400ms
Enter
Sleep 5s

Sleep 2s
