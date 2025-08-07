# LinkedIn-Engagement

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Python-based automation suite for LinkedIn engagement, including post retrieval, liking, commenting, and AI-powered comment generation. Designed to help businesses and professionals streamline outreach, interaction, and data collection on LinkedIn.

## 🚀 Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Data-Carlos/LinkedIn-engagement.git
   cd LinkedIn-engagement
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys and LinkedIn credentials
   ```

5. **Run your first automation:**

   ```bash
   python linkedin_commenter.py
   ```

## ✨ Features

- 🔗 Build and maintain LinkedIn graph stored in SQLite
- 📊 Retrieve posts from first-degree connections and target prospects
- 👍 Automatically like posts from the fetched dataset
- 🤖 AI-generated comments using OpenAI and Google Generative AI
- 💬 Post generated comments on LinkedIn
- 📝 Structured logging and CSV export for audit and analysis
- ⏰ Configurable scheduling within scripts

## 📁 Project Structure

```text
linkedin-engagement/
├── backend/                     # Core services and graph logic
│   ├── invitations/            # Invitation graph and SQLite service
│   └── linkedin/               # LinkedIn graph, nodes, and storage service
├── scripts/                    # Main automation scripts
├── tests/                      # Test files
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
├── LICENSE                    # MIT License
└── README.md                  # This file
```

## 🔧 Configuration

Copy `.env.example` to `.env` and configure the following variables:

```ini
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_google_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Required LinkedIn Credentials
LINKEDIN_USERNAME=your_linkedin_email@example.com
LINKEDIN_PASSWORD=your_linkedin_password

# Optional Configuration
DB_PATH=./linkedin_project_db.sqlite3
LOG_LEVEL=INFO
RATE_LIMIT_DELAY=2
```

## 📋 Usage

### Retrieve Posts

From first-degree connections:

```bash
python retrieve_post_1stconnections.py
```

From target prospects list:

```bash
python retrieve_posts_prospects.py --input prospects.csv
```

### Engagement Actions

Like posts:

```bash
python linkedin_post_liker.py --source posts.csv
```

Generate AI comments:

```bash
python comment_generator.py --source posts.csv --output comments.csv
```

Post comments:

```bash
python linkedin_commenter.py --source comments.csv
```

### Automation

Set up automated workflows:

```bash
bash linkedin_automation.sh
```

## 🗄️ Database

The application uses SQLite for data persistence:

- `linkedin_project_db.sqlite3` - Main database storing graph data and posts
- `linkedin_project_db.sqlite3-shm` - Shared memory file for WAL mode
- `linkedin_project_db.sqlite3-wal` - Write-ahead log for atomic transactions

## 📊 Logging and Reports

All scripts generate detailed logs and CSV reports:

- `*.log` files contain execution logs
- CSV exports include engagement metrics and audit trails
- Reports are saved in the project root for analysis

## 🧪 Testing

Run the test suite:

```bash
python -m pytest tests/
```

Run specific tests:

```bash
python -m pytest tests/test_rate_limiting.py -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and automation purposes. Please ensure you comply with LinkedIn's Terms of Service and use this responsibly. The authors are not responsible for any misuse or violations.

## 🙏 Acknowledgments

- OpenAI for GPT API
- Google for Gemini API
- Tavily for search capabilities
- The Python community for excellent libraries