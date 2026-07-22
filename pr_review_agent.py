from openai import OpenAI
from pathlib import Path
import os
import requests
 
client = OpenAI()
 
def read_pr_context():
    context = []
    context.append("FILES CHANGED:")
    for file in Path(".").rglob("*"):
        if file.is_file():
            context.append(str(file))
    return "\n".join(context)

def review_pull_request(context):

    prompt = f"""
You are a senior DevOps reviewer.
 
Review the following pull request changes.
 
Identify:- Risks- Missing tests- Infrastructure concerns
 
Respond with:- Summary- Risks- Recommendations
 
Context:
{context}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a careful DevOps reviewer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    context = read_pr_context()
    review = review_pull_request(context)
 
    repo = os.environ["REPO"]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GH_TOKEN"]
 
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"Bearer {token}"}
    result = requests.post(url, headers=headers, json={"body": f"AI Review Summary:\n\n{review}"})
 
    print("GitHub response status:", result.status_code)
    print(result.text)
    print(review)