# LeetCode AI Agent

A terminal-based LeetCode practice coach. Chat naturally to get a problem, ask for another one, request its link, and record problems you solve.

## Setup

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and an OpenAI API key.

1. Clone this repository and open its directory.
2. Create a `.env` file in the project root containing:

   ```dotenv
   OPENAI_API_KEY=your_api_key_here
   ```

3. Install dependencies and start the chat:

   ```bash
   uv sync
   uv run leetcodeagent
   ```

Type `exit`, `quit`, or `q` to leave the chat.

## Example prompts

```text
Give me a random LeetCode problem.
I'd like an easy array problem.
Skip that one and give me another.
What's the link to the last problem?
I solved it.
Which problems have I solved?
Delete 1. Two Sum | Easy from memory.
```

For a first recommendation without a difficulty, the coach asks whether you want easy, medium, or hard. Later requests can reuse the previous difficulty. Recommendations include a link to the problem.

## How it works

- Public problem metadata comes from LeetCode's website GraphQL endpoint. The agent filters out paid problems and problems already recorded as solved, then uses NumPy to choose a candidate.
- Solved problems are stored locally in `src/leetcodeagent/memory.md`, one per line, for example `- 1. Two Sum | Easy`. The coach does not read your LeetCode account or submission history.
- The model decides when to call the recommendation, link, and memory tools. Deleting a memory entry asks for terminal confirmation.

LeetCode's website endpoint is undocumented and may change or reject requests. A network connection is needed for fresh recommendations, and an OpenAI API key is needed for chat.
