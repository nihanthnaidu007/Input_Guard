from __future__ import annotations

from typing import Dict, List


_RECOMMENDATIONS: Dict[str, Dict[str, str]] = {
    "programming language": {
        "gap": "programming language",
        "what_is_missing": "You haven't told it which programming language or technology to use.",
        "what_to_provide": "Add something like 'using Python', 'in JavaScript with React', or 'with Node.js'. If you're not sure which to use, say what device or platform you want it to run on, like 'runs in a web browser' or 'runs on my Mac'.",
        "why_it_matters": "Without this, the AI picks a language on its own. You might get something built in a language you don't have installed or can't run on your machine.",
    },
    "api structure": {
        "gap": "api structure",
        "what_is_missing": "You mentioned an API but didn't describe what it should do or how it should work.",
        "what_to_provide": "Describe the actions it needs to support. For example: 'it needs to get a list of users, create a new user, and delete a user by their ID'. You don't need to use technical terms, just describe what it does.",
        "why_it_matters": "Without this, the AI invents its own structure. You will spend hours correcting routes, field names, and data shapes you never asked for.",
    },
    "data model": {
        "gap": "data model",
        "what_is_missing": "You mentioned storing data but didn't say what data or what details need to be saved.",
        "what_to_provide": "List the main things you need to store and what information matters for each. For example: 'store users with their name, email address, and password' or 'products with a title, price, and how many are in stock'.",
        "why_it_matters": "Without this, the AI guesses your entire database structure. The names, fields, and data types will be wrong and you will have to rebuild them from scratch.",
    },
    "integration specifics": {
        "gap": "integration specifics",
        "what_is_missing": "You mentioned a third-party service but didn't say which part of it you need or what you want it to do.",
        "what_to_provide": "Be specific about what action you need. For example, with Stripe say 'accept one-time payments' or 'handle monthly subscriptions'. With Twilio say 'send SMS notifications when an order ships'. With AWS S3 say 'let users upload and download profile photos'.",
        "why_it_matters": "These services have dozens of features. Without a specific one, the AI picks something at random that may not match what you actually need.",
    },
    "authentication type": {
        "gap": "authentication type",
        "what_is_missing": "You mentioned login or authentication but didn't say what kind.",
        "what_to_provide": "Pick one and name it. Common options: 'email and password login', 'login with Google', 'login with GitHub', 'API key', 'magic link sent to email'. If you're not sure, say 'simple email and password login' and that will work for most apps.",
        "why_it_matters": "Each authentication type is built completely differently. Choosing the wrong one means a full rebuild later. Naming one now saves that problem entirely.",
    },
    "output format": {
        "gap": "output format",
        # Shared gap string, two senses (coding + data analysis — eval-pinned
        # vocabulary): the advice names the deliverable in both worlds.
        "what_is_missing": "You didn't say what kind of result you want — what should exist when this is done, and how will it be used?",
        "what_to_provide": "Add something like: 'as a web app I can open in a browser', 'as a command-line tool', 'as a REST API' — or, for an analysis: 'a bar chart', 'a one-page summary', 'a trends table', or 'a dashboard'. Pick whichever matches how you plan to use it.",
        "why_it_matters": "A web app, a script, an API, and a summary chart that do the same job look completely different in code. Without this, the AI picks one and you might get the wrong one entirely.",
    },
    "dataset/source": {
        "gap": "dataset/source",
        "what_is_missing": "You haven't named the data to analyze — no file, table, export, or database is referenced.",
        "what_to_provide": "Point to the data by name: 'sales_2026.csv', 'the attached export', 'the subscriptions table in postgres', or 'the GA4 export'. 'My data' or 'this dataset' isn't enough for it to know where to look.",
        "why_it_matters": "Without a named source, the AI has to invent one or ask you anyway. Naming the exact file or table gets you analysis of YOUR data on the first try instead of a template with placeholder numbers.",
    },
    "question/goal": {
        "gap": "question/goal",
        "what_is_missing": "You haven't said what question the analysis should answer or what decision it should inform.",
        "what_to_provide": "State the question or goal explicitly: 'did refunds spike after the pricing change?', 'which plan tier cancels most?', 'I want a cohort retention view'. One sentence is enough.",
        "why_it_matters": "Without a question, you get a generic summary of everything. With one, the analysis is focused, faster, and actually answers what you needed to know.",
    },
    "tooling": {
        "gap": "tooling",
        "what_is_missing": "You haven't said which tool or language the analysis should use.",
        "what_to_provide": "Name the tooling: 'in Python with pandas', 'SQL only', 'in BigQuery', 'statsmodels', or 'no external libraries'. If it doesn't matter, say 'any tool is fine'.",
        "why_it_matters": "Different tools mean different workflows. The AI may produce a Python script when your team runs dbt, or SQL your warehouse can't run — naming the tool keeps the output usable as-is.",
    },
    "volume": {
        "gap": "volume",
        "what_is_missing": "You haven't said how much data is involved.",
        "what_to_provide": "State the scale: 'about 80,000 rows', 'two years of daily data', '5,000 survey responses', or 'a 400M-row event table'. Row counts, file sizes, or date ranges all work.",
        "why_it_matters": "Scale changes the approach. A quick pandas script dies at 400M rows; a full warehouse job is overkill for 500. Saying the size gets you a method that actually runs.",
    },
    "reproducibility": {
        "gap": "reproducibility",
        "what_is_missing": "You haven't said whether this is a one-off or needs to be rerun.",
        "what_to_provide": "Say how it will be reused: 'rerun weekly', 'a one-off look', 'document the steps so the team can reproduce it', or 'make the query reusable for every launch'.",
        "why_it_matters": "One-off looks and recurring reports are built differently. Saying which one it is decides whether you get a quick answer or a documented, rerunnable pipeline.",
    },
    "task context": {
        "gap": "task context",
        "what_is_missing": "Your request doesn't include enough detail for anyone to know what to build.",
        "what_to_provide": "Describe what you want to build and how you plan to use it. For example: 'I want to build a web app where users can log in and track their daily expenses' or 'I need a Python script that reads a CSV file and sends a summary email'. The more specific you are, the closer the AI gets to what you actually want on the first try.",
        "why_it_matters": "Without basic context, the AI has to guess the language, the kind of app, the data it stores, and what it does. Almost every guess will be wrong, and you will spend more time correcting than building.",
    },
    "error description": {
        "gap": "error description",
        "what_is_missing": "You haven't shared the actual error message, exception, or output you're seeing.",
        "what_to_provide": "Include the exact error message or exception you are seeing. Copy and paste it exactly as it appears. For example: 'I'm getting TypeError: cannot read property of undefined on line 23' or 'it throws a 500 Internal Server Error with message: connection refused'. The exact wording tells the AI exactly what went wrong.",
        "why_it_matters": "Without the exact error, the AI has to guess what failure mode you're hitting. The wrong guess sends you down a fix path that doesn't apply to your actual problem.",
    },
    "expected vs actual behavior": {
        "gap": "expected vs actual behavior",
        "what_is_missing": "You haven't described what you expected to happen and what is actually happening.",
        "what_to_provide": "Describe two things: what you expected to happen, and what actually happened. For example: 'I expected the function to return a list of users, but it returns an empty list every time' or 'the button should submit the form but nothing happens when I click it'. Without this, the AI is guessing what the problem is.",
        "why_it_matters": "A bug is the gap between what you wanted and what happened. Without both sides, the AI cannot tell what counts as a fix.",
    },
    "code context": {
        "gap": "code context",
        "what_is_missing": "You haven't pointed to a language, file, function, or snippet for the AI to look at.",
        "what_to_provide": "Tell it which language you are using and point to the specific part of your code that has the problem. For example: 'this is a Python function called get_users()' or 'this is in my React component UserList.jsx on line 45'. The more specific you are, the more targeted the fix will be.",
        "why_it_matters": "Without a code reference, the AI suggests generic fixes that may not apply to your actual code. Pointing to the exact location lets it propose a precise change.",
    },
    "optimization target": {
        "gap": "optimization target",
        "what_is_missing": "You haven't named the specific function, component, or section to optimize.",
        "what_to_provide": "Tell it exactly which part of your code you want to optimize. For example: 'the get_users() function takes 3 seconds to run' or 'the database query on line 45 of users.py is very slow' or 'the React component re-renders too many times'. Saying 'my app' is too broad. Point to the specific function or component.",
        "why_it_matters": "Without a target, the AI optimizes whatever it guesses and may rewrite the wrong code. Specificity prevents broad, unhelpful refactors.",
    },
    "performance baseline": {
        "gap": "performance baseline",
        "what_is_missing": "You haven't described how slow or resource-heavy the code currently is.",
        "what_to_provide": "Describe how slow or inefficient it currently is. For example: 'it takes about 8 seconds to load' or 'memory usage spikes to 2GB when processing large files' or 'users are complaining about a 5-second delay'. A specific measurement helps the AI suggest the right kind of fix.",
        "why_it_matters": "Different baselines call for different fixes. Trimming 100ms off a request looks nothing like cutting an 8-second response in half.",
    },
    "optimization constraint": {
        "gap": "optimization constraint",
        "what_is_missing": "You haven't said what must stay the same or what tradeoffs are acceptable.",
        "what_to_provide": "Tell it what you cannot or do not want to change. For example: 'it must stay backward compatible' or 'readability is more important than speed' or 'I cannot change the database schema'. Without this, the AI might suggest a technically faster solution that breaks something else you care about.",
        "why_it_matters": "Every optimization is a tradeoff. Without your constraints, the AI may produce a faster version that breaks API contracts, harms readability, or forces a schema migration.",
    },
    "code reference": {
        "gap": "code reference",
        "what_is_missing": "You haven't pointed to the specific code, function, or concept you want explained.",
        "what_to_provide": "Point to the specific thing you want explained. For example: 'explain what the @property decorator does in Python' or 'explain what this async/await block is doing' or 'explain how the useEffect hook works in React'. Without a specific reference, the AI will give a generic answer that may not address what is actually confusing you.",
        "why_it_matters": "A vague 'explain this' leads to a generic textbook answer. Naming the exact concept anchors the explanation to what you actually need to understand.",
    },
    "explanation depth": {
        "gap": "explanation depth",
        "what_is_missing": "You haven't said how deep or simple you want the explanation to be.",
        "what_to_provide": "Say how much detail you want. For example: 'give me a simple one-paragraph overview' or 'explain it step by step like I have never used Python before' or 'go deep into how it works under the hood'. Without this, the AI picks a depth that might be too basic or too technical.",
        "why_it_matters": "An explanation aimed at the wrong level is wasted. Setting depth up front lets the AI calibrate to your background and goal.",
    },
    "existing stack": {
        "gap": "existing stack",
        "what_is_missing": "You haven't said what language, framework, or tech stack your existing app is built with.",
        "what_to_provide": "Tell it what your app is already built with. For example: 'my app is built with React on the frontend and FastAPI on the backend' or 'this is a Node.js Express app using MongoDB'. Without this, the AI might suggest an implementation that conflicts with your existing code.",
        "why_it_matters": "A feature added in the wrong stack will not drop in cleanly. The AI may produce code that does not match your conventions or imports.",
    },
    "feature scope": {
        "gap": "feature scope",
        "what_is_missing": "You named the feature but didn't describe what it should actually do.",
        "what_to_provide": "Define exactly what the feature should do. For example, if you want search: 'search by product name and description, case-insensitive, show results as you type' is specific. 'Add search' is not. A clear scope means the AI builds what you actually need instead of a generic version you will have to rewrite.",
        "why_it_matters": "Without a scope, the AI implements a generic version that probably misses your real requirements and forces a rewrite.",
    },
    "completion criteria": {
        "gap": "completion criteria",
        "what_is_missing": "You haven't described what 'done' looks like for this feature.",
        "what_to_provide": "Describe what done looks like. For example: 'the feature is complete when a user can type in the search box and see matching results appear within 200ms' or 'done means the user receives an email notification within 30 seconds of placing an order'. This prevents the AI from stopping too early or going too far.",
        "why_it_matters": "Without a clear definition of done, the AI may ship a half-finished feature or over-engineer something well past what you needed.",
    },
    "audience": {
        "gap": "audience",
        "what_is_missing": "You haven't said who will read this.",
        "what_to_provide": "Name the reader and what they already know. For example: 'for the executive team, keep it high-level', 'for beginners who have never used the tool', 'for the client stakeholders, no jargon'. Even one phrase like 'for my manager' sharpens the tone and level of detail.",
        "why_it_matters": "The same topic reads completely differently for a CEO, a new hire, or a customer. Without a named reader, the AI aims the piece at nobody in particular.",
    },
    "purpose": {
        "gap": "purpose",
        "what_is_missing": "You haven't said what this piece should accomplish.",
        "what_to_provide": "State the goal in one phrase: 'to persuade the steering committee to fund Q1 headcount', 'to announce the launch', 'to explain why the deadline moved'. A goal like 'convince', 'inform', or 'ask for' is enough to aim the writing.",
        "why_it_matters": "Informing and persuading lead to different structures, evidence, and tone. Without a goal, the AI produces a generic piece that does neither well.",
    },
    "structure/format": {
        "gap": "structure/format",
        "what_is_missing": "You haven't said how long the piece should be or how it should be organized.",
        "what_to_provide": "Give a length and a shape. For example: 'under 300 words', 'one page', 'bullets with a short intro', 'three sections: situation, options, recommendation'. Any constraint — even just 'keep it short' — works.",
        "why_it_matters": "Without length or organization guidance, the AI picks its own shape. You will often get a bloated draft you then have to cut down yourself.",
    },
    "source material": {
        "gap": "source material",
        "what_is_missing": "You asked to work on existing text but didn't provide it.",
        "what_to_provide": "Paste the text you want reworked — the draft, notes, or paragraph — directly into the message, or point to where it lives ('the outline is at the bottom'). Include any version details that matter.",
        "why_it_matters": "The AI cannot see text that isn't in the message. Without it, you get a generic rewrite of an imaginary document instead of an improvement to yours.",
    },
    "context": {
        "gap": "context",
        "what_is_missing": "You haven't said what the piece is about or what situation it responds to.",
        "what_to_provide": "Name the subject and the situation. For example: 'about remote work for our company blog', 'regarding the Q3 roadmap', 'the email should tell the team the migration finished'. One sentence of background is enough.",
        "why_it_matters": "Without a topic or situation, there is nothing to write about. The AI either invents one or asks you everything you could have said up front.",
    },
    "completeness": {
        "gap": "completeness",
        "what_is_missing": "You haven't listed anything the piece must include.",
        "what_to_provide": "Name the must-haves: 'include the headline, a quote from the CEO, and pricing', 'must cover current costs, risks, and the timeline', 'mention the new ship date'. Also note any hard limits, like a word count.",
        "why_it_matters": "Must-have details left out of the request get left out of the draft. Naming them up front saves a second pass to work them in.",
    },
}


def _fallback_recommendation(gap: str) -> Dict[str, str]:
    """Generic four-key advice for a gap with no curated entry.

    The documented fallback (spec art_bTvdPdJS §6): unknown gaps keep their
    advice complete instead of vanishing silently from the recommendations
    list — the v0.2 behavior that let rule authors ship empty advice.
    """
    return {
        "gap": gap,
        "what_is_missing": f"You haven't provided the {gap} needed to act on this request.",
        "what_to_provide": f"Describe the {gap} explicitly — one or two concrete sentences is enough.",
        "why_it_matters": f"Without the {gap}, the request can be read several ways and the answer may miss what you actually need.",
    }


def get_recommendations(gaps: List[str]) -> List[Dict[str, str]]:
    """Build one four-key recommendation per gap, in input order.

    A gap without a curated entry gets the documented fallback
    (see :func:`_fallback_recommendation`) — never a silent drop.
    """
    out: List[Dict[str, str]] = []
    for gap in gaps:
        entry = _RECOMMENDATIONS.get(gap)
        out.append(dict(entry) if entry is not None else _fallback_recommendation(gap))
    return out
