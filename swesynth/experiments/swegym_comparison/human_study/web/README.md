# Bug Classification Study

This is a web application for conducting a human study to determine if synthetic bugs align with real-world issues. The study presents users with code snippets containing bugs and asks them to classify each bug as either "synthetic" (artificially created) or "real" (from real-world applications).

## Purpose

The goal of this study is to determine if synthetic bugs are in the same distribution as real-world bugs, by testing if humans can reliably distinguish between them. If humans cannot tell the difference (accuracy around 50%), it suggests that the synthetic bugs align well with real-world issues.

## Features

- Multi-user support with user registration and authentication
- Randomly displays either synthetic or real bug code snippets
- Collects and persists user responses to JSON files
- Measures response time for each classification
- Calculates statistical results including:
  - Proportion of correct classifications
  - Confidence intervals
  - P-value against random guessing (50%)
- Provides interpretation of results
- Admin dashboard for researchers to analyze all collected data
- Data export functionality for further analysis

## Getting Started

### Prerequisites

- Node.js 18.0.0 or higher
- npm or yarn

### Installation

1. Clone the repository
2. Navigate to the project directory
3. Install dependencies:

```bash
npm install
# or
yarn install
```

### Running the Application

1. Start the development server:

```bash
npm run dev
# or
yarn dev
```

2. Open your browser and navigate to `http://localhost:3000`

### Data Files

The application uses two JSONL files to store bug data:

- `public/data/rq8_all_fake_bug_sample200.jsonl` - Contains synthetic bug examples
- `public/data/rq8_all_real_bug_sample200.jsonl` - Contains real-world bug examples

Each line in these files represents a single bug with the following format:

```json
{"instance_id": "unique_id", "model_patch": "code_with_bug", "problem_statement": "description_of_the_bug"}
```

### User Data Storage

The application stores user data in JSON files in the `data` directory:

- `data/users.json` - Contains registered user information
- `data/responses/[user_id].json` - Contains classification responses for each user

## User Flow

1. **Registration**: Users provide their name and email to register
2. **Classification**: Users view bug code snippets and classify them as synthetic or real
3. **Results**: After classifying at least 10 bugs, users can view their results with statistical analysis

## Admin Dashboard

An admin dashboard is available at `/admin` for researchers to:

- View aggregated statistics across all users
- Analyze individual user performance
- View confusion matrix and response time metrics
- Download all collected data for further analysis

Access the admin dashboard with password: `admin123`

## Adding More Bugs

To add more bugs to the study, simply add more JSON lines to the appropriate JSONL file:

- For synthetic bugs: `public/data/rq8_all_fake_bug_sample200.jsonl`
- For real bugs: `public/data/rq8_all_real_bug_sample200.jsonl`

## Analyzing Results

The application provides several views for analyzing results:

1. **Individual Results**: Each user can see their own performance metrics after completing classifications
2. **Admin Dashboard**: Researchers can see aggregate results and individual breakdowns
3. **Data Export**: All data can be exported as JSON for further analysis in statistical software
