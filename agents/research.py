#!/usr/bin/env python3
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig
from datetime import datetime

# Load environment variables
load_dotenv()


async def save_knowledge_base(content: str, path: Path):
    """Helper to save content to disk in a thread to keep async loop free."""
    def _save():
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    await asyncio.to_thread(_save)


async def perform_research(api_key: str, domain: str = "AI and Software Development"):
    print(f'🚀 Performing deep research on domain: {domain}...')

    current_date_str = datetime.now().strftime("%B %d, %Y")
    current_date_short = datetime.now().strftime("%Y-%m-%d")
    
    # Create clean filename for any domain
    domain_slug = domain.replace(" ", "_").replace("/", "_").replace("&", "and")
    filename = f"{domain_slug}_Update_{current_date_short}.txt"

    client = genai.Client(api_key=api_key)
    model_id = "gemini-3-flash-preview"   # Change to gemini-2.5-pro or gemini-2.0-flash-exp if you want even better quality

    tools = [{"google_search": {}}]

    prompt = f"""
You are an expert researcher creating a daily knowledge base for an AI agent that engages on X (Twitter) in the "{domain}" space.

Current real date: {current_date_str}
Domain: {domain}

Your task is to create a COMPREHENSIVE, highly detailed knowledge base in EXACTLY this format:

**{domain_slug}_Update_{current_date_short}.txt**

--- Update Log ---
Date: {current_date_str}
Purpose: Comprehensive roundup of key events, trends, releases, and concepts in the "{domain}" space from late 2025 to today. This ensures the AI agent is fully up-to-date and never sounds outdated when engaging on X.

--- Section 1: Key Trends for 2026 (Expanded with Practical Implications) ---
List 8-10 major trends in {domain}. For each trend write 2-3 sentences including what someone in this space should know or do.

--- Section 2: Major Releases and Updates in 2026 ---
Detail the top 5-7 most important releases, products, albums, tools, laws, or updates specific to {domain}. Include dates, key details, and why they matter.

--- Section 3: Key Tools, Platforms and Resources ---
List 10-15 of the most useful tools, platforms, apps, or resources in {domain} with short use-case descriptions.

--- Section 4: Recent News Items (Chronological, 2026 Focus) ---
Keep a running list of major stories from Jan–March 2026 (summarize older ones briefly).

--- Section 5: Industry Shifts and Practical Changes ---
Deeper analysis of how the industry is changing (career impact, new skills needed, cultural shifts, etc.).

--- Section 6: X Ecosystem Insights ---
What people are actually discussing on X right now in the {domain} community.

--- Section 7: News Today ({current_date_short}) — ONLY Fresh Items from Today ---
Strictly only news published or updated TODAY ({current_date_str}). For each item:
• **Bold title**
• 2-3 sentence rich summary
• Why it matters: (one line perfect for X engagement)
• Source (if available)

RESEARCH INSTRUCTIONS:
- Use the google_search tool aggressively to get the absolute latest news (especially for Section 7).
- Adapt EVERYTHING perfectly to the domain "{domain}". Examples:
  - If domain = "Stand-up Comedy" → talk about specials, Netflix deals, AI joke writers, TikTok virality, etc.
  - If domain = "Music Production" → talk about new DAWs, AI stem separation, streaming payouts, festival lineups, etc.
  - If domain = "Fitness" → talk about new wearables, AI trainers, training methodologies, etc.
- Make the entire document 2000-3500 words, professional yet conversational, extremely detailed and current.
- Output ONLY the final text file content starting from "**{domain_slug}_Update_{current_date_short}.txt**". 
  No explanations, no markdown code blocks, no extra text.

Begin now.
"""

    try:
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=GenerateContentConfig(
                tools=tools,
                temperature=0.7,
            )
        )

        result = response.text.strip()
        if not result:
            print("❌ Empty result from LLM.")
            return None

        # Save to data folder with dynamic filename
        from agents import DATA_DIR
        DATA_DIR.mkdir(exist_ok=True)
        abs_output_file = DATA_DIR / filename

        await save_knowledge_base(result, abs_output_file)
        print(f'✅ Successfully created knowledge base: {abs_output_file}')
        return result

    except Exception as e:
        print(f'❌ Error during research: {str(e)}')
        return None


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Universal Domain Knowledge Base Generator')
    parser.add_argument('--domain', type=str, default='AI and Software Development',
                        help='Domain to research (e.g. "Stand-up Comedy", "Music Production", "Fitness", "Fashion", "Cooking")')
    args = parser.parse_args()

    google_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not google_key:
        print('❌ Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable')
    else:
        asyncio.run(perform_research(google_key, args.domain))