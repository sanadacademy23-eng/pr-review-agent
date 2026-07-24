from openai import OpenAI
from pathlib import Path
import os
import requests
import sys
import json

 
client = OpenAI()
 
def read_pr_context():
    repo = os.environ["REPO"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GH_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    response = requests.get(url, headers=headers)

    # Safety Net 1: Catch GitHub API errors immediately
    if response.status_code != 200:
        print(f"Error fetching PR files: {response.status_code} {response.text}")
        return "CHANGES IN THIS PULL REQUEST:\n(Error fetching files)"

    files = response.json()

    context = ["CHANGES IN THIS PULL REQUEST (Git Diff Format):"]

    for file in files:
        context.append(f"\nFile: {file.get('filename', 'Unknown')} (Status: {file.get('status', 'unknown')})")
        patch = file.get("patch")
        if patch:
            context.append(patch)
        else:
            context.append("(No inline diff provided by GitHub API. Text changes are empty.)")

    return "\n".join(context)

def review_pull_request(context):
    prompt = f"""
    You are a strict DevOps gatekeeper reviewing a pull request.
    Judge ONLY the changes shown below. The changes are provided in Git diff format. 
    Lines starting with '+' are NEW lines being added to the code.

    Respond ONLY with a valid JSON object in exactly this structure:
    {{
      "decision": "PASS" or "FAIL",
      "reason": "One or two sentences explaining the decision."
    }}

    Return "FAIL" if the added lines (the '+' lines) contain ANY hardcoded secret, credential, API key, password, or obviously dangerous command. 
    CRITICAL RULE: You must return "FAIL" even if the credential appears to be a fake, dummy, or example key.

    Otherwise return "PASS".

    Changes:
    {context}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a strict DevOps reviewer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

if __name__ == "__main__":
    context = read_pr_context()

    print("=== PR CONTEXT SENT TO AI ===")
    print(context)
    print("=============================")

    raw_review = review_pull_request(context)

    # Safety Net 2: Strip markdown formatting if the AI gets too helpful
    clean_review = raw_review.replace("```json", "").replace("```", "").strip()

    repo = os.environ["REPO"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GH_TOKEN"]
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"Bearer {token}"}

    # Post the comment back to the PR
    requests.post(url, headers=headers, json={"body": f"AI Review Summary:\n```json\n{clean_review}\n```"})

    try:
        review_data = json.loads(clean_review)
        decision = review_data.get("decision", "FAIL")
        reason = review_data.get("reason", "No reason provided.")
    except json.JSONDecodeError:
        decision = "FAIL"
        reason = f"Agent failed to return valid JSON. Raw output: {clean_review}"

    print(f"Gatekeeper decision: {decision}")
    print(f"Reason: {reason}")

    if decision == "FAIL":
        print("Pipeline blocked. Exiting with error code 1.")
        sys.exit(1)
    else:
        print("Code approved. Exiting cleanly.")
        sys.exit(0)