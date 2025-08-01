# Soterix QA Automation - Python Playwright Framework

This repository contains automated test scripts for the Videonetics VSaaS platform using [Playwright](https://playwright.dev/python/) with **Python 3.11** and **pytest**.

> 🛠️ This repo replaces the legacy Selenium demo with a modern Python-based Playwright testing framework. It follows a Page Object Model structure and supports multi-tenancy, QA Touch integration, and is designed for use by both onshore and offshore QA teams.

---

## ✅ Prerequisites

### 1. 🐍 Install Python 3.11
- Download from: [https://www.python.org/downloads/release/python-3110/](https://www.python.org/downloads/release/python-3110/)
- During installation:
  - ✅ Check **“Add Python to PATH”**
  - ✅ Ensure **pip** is enabled

### 2. 💻 VS Code Setup (Recommended)
- Install [Visual Studio Code](https://code.visualstudio.com/)
- Install the following extensions:
  - Python
  - Pylance
  - Playwright Test for VS Code (optional)
  
---

## 🔧 Environment Setup

### 1. Create a Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On Mac/Linux
