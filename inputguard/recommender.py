from __future__ import annotations

from typing import Dict, List


_RECOMMENDATIONS: Dict[str, dict] = {
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
        "what_is_missing": "You didn't say what kind of thing you're building or how it will be used.",
        "what_to_provide": "Add something like: 'as a web app I can open in a browser', 'as a command-line tool I run in my terminal', 'as a REST API', 'as a Python script', or 'as a mobile app'. Pick whichever matches how you plan to use it.",
        "why_it_matters": "A web app, a script, and an API that do the same job look completely different in code. Without this, the AI picks one and you might get the wrong one entirely.",
    },
    "task context": {
        "gap": "task context",
        "what_is_missing": "Your request doesn't include enough detail for anyone to know what to build.",
        "what_to_provide": "Describe what you want to build and how you plan to use it. For example: 'I want to build a web app where users can log in and track their daily expenses' or 'I need a Python script that reads a CSV file and sends a summary email'. The more specific you are, the closer the AI gets to what you actually want on the first try.",
        "why_it_matters": "Without basic context, the AI has to guess the language, the kind of app, the data it stores, and what it does. Almost every guess will be wrong, and you will spend more time correcting than building.",
    },
}


def get_recommendations(gaps: List[str]) -> List[dict]:
    out: List[dict] = []
    for gap in gaps:
        if gap in _RECOMMENDATIONS:
            out.append(dict(_RECOMMENDATIONS[gap]))
    return out
