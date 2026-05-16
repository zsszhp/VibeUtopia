import os
import re
import urllib.request
import subprocess

MD_PATH = "references/参考论文与开源项目.md"
PAPERS_DIR = "references/papers"
PROJECTS_DIR = "references/projects"

os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(PROJECTS_DIR, exist_ok=True)

with open(MD_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Extract and download arXiv papers
arxiv_links = re.findall(r'https://arxiv\.org/abs/(\d+\.\d+)', content)
print(f"Found {len(arxiv_links)} arXiv papers.")
for paper_id in set(arxiv_links):
    pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
    pdf_path = os.path.join(PAPERS_DIR, f"{paper_id}.pdf")
    if not os.path.exists(pdf_path):
        print(f"Downloading {paper_id}.pdf...")
        try:
            urllib.request.urlretrieve(pdf_url, pdf_path)
            print(f"Successfully downloaded {paper_id}.pdf")
        except Exception as e:
            print(f"Failed to download {paper_id}: {e}")
    else:
        print(f"{paper_id}.pdf already exists.")

# 2. Extract and clone github projects
github_links = re.findall(r'https://github\.com/([\w\-]+/[\w\-]+)', content)
print(f"\nFound {len(github_links)} GitHub projects.")
for repo in set(github_links):
    repo_name = repo.split('/')[-1]
    repo_url = f"https://github.com/{repo}.git"
    repo_path = os.path.join(PROJECTS_DIR, repo_name)
    if not os.path.exists(repo_path):
        print(f"Cloning {repo}...")
        try:
            subprocess.run(["git", "clone", "--depth", "1", repo_url, repo_path], check=True)
            print(f"Successfully cloned {repo}")
        except Exception as e:
            print(f"Failed to clone {repo}: {e}")
    else:
        print(f"Project {repo_name} already cloned.")

print("\nAll downloads completed.")
