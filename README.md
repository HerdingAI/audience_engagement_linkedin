# LinkedIn-Engagement

A Python-based automation suite for LinkedIn engagement, including post retrieval, liking, commenting, and AI-powered comment generation. Designed to help businesses and professionals streamline outreach, interaction, and data collection on LinkedIn.

## Features

- Retrieve posts from first-degree connections and target prospects
- Automatically like and comment on selected posts
- AI-generated comments using OpenAI and Google Generative AI
- Configurable scheduling via Python `schedule` or cron jobs
- Structured logging and CSV export for audit and analysis
- Modular backend services for invitations and LinkedIn graph management

## Directory Structure

```
/ (root)
├─ backend/                           # Core services and graph logic
│  ├─ invitations/                   # Invitation graph and SQLite service
│  └─ linkedin/                      # LinkedIn graph, nodes, and storage service
├─ Code_W_Other_API_Endpoints/       # Custom endpoint integrations
├─ multimedia/                       # Downloaded media assets
├─ *.py                              # Main scripts (retrieval, liking, commenting, generation)
├─ requirements.txt                  # Python dependencies
├─ setup_automation.sh               # Automated setup script
├─ crontab_setup.txt                 # Cron job configuration
├─ .env                              # Environment variables
└─ README.md                         # Project overview (this file)
```

## Getting Started

### Prerequisites

- Python 3.10+ installed
- A valid LinkedIn account
- OpenAI and/or Google Generative AI API key(s)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Data-Carlos/LinkedIn-engagement.git
   cd LinkedIn-engagement
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

1. Copy `.env.example` to `.env` (or create a new `.env` file in root):
   ```bash
   cp .env.example .env
   ```
2. Populate the following environment variables in `.env`:
   ```ini
   LINKEDIN_USERNAME=<your_linkedin_email>
   LINKEDIN_PASSWORD=<your_linkedin_password>
   OPENAI_API_KEY=<your_openai_key>
   GOOGLE_API_KEY=<your_google_ai_key>       # optional
   DB_PATH=./linkedin_project_db.sqlite3
   ```

### Usage

#### Retrieve Posts

- From first-degree connections:
  ```bash
  python retrieve_post_1stconnections.py
  ```
- From target prospects list:
  ```bash
  python retrieve_posts_prospects.py --input prospects.csv
  ```

#### Engagement Actions

- Like posts:
  ```bash
  python linkedin_post_liker.py --source posts.csv
  ```
- Generate comments using AI:
  ```bash
  python comment_generator.py --source posts.csv --output comments.csv
  ```
- Post comments:
  ```bash
  python linkedin_commenter.py --source comments.csv
  ```
- Combined posting and generation sequence:
  ```bash
  sh setup_automation.sh
  ```

### Scheduling

- Use Python scheduler within scripts to run at intervals.
- Or configure a cron job described in `crontab_setup.txt`:
  ```bash
  crontab crontab_setup.txt
  ```

## Logs and Reports

All scripts write detailed logs to `*.log` files in root. CSV exports of comments, prospects, and engagement metrics are saved alongside logs for review.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xyz`)
3. Commit your changes (`git commit -m "Add xyz feature"`)
4. Push to your branch (`git push origin feature/xyz`)
5. Open a Pull Request

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.