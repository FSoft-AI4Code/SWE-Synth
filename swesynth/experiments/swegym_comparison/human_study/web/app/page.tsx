"use client";

import { useState, useEffect } from "react";
import { DiffEditor } from "@monaco-editor/react";
import ReactMarkdown from 'react-markdown';

type BugType = "synthetic" | "real";

interface User {
  id: string;
  name: string;
  email: string;
}

interface Bug {
  instance_id: string;
  model_patch: string;
  problem_statement: string;
  issue_description: string;
  type: BugType; // The actual type of the bug
}

interface UserResponse {
  bug_id: string;
  actual_type: BugType;
  user_response: BugType;
  correct: boolean;
  response_time: number;
}

// Implementation of the error function (erf)
// This approximation is from Abramowitz and Stegun (1964)
function erf(x: number): number {
  // Constants
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  // Save the sign of x
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);

  // Formula
  const t = 1.0 / (1.0 + p * x);
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);

  return sign * y;
}

// Extract the original and modified code from the diff
function extractDiffContent(diffText: string): { original: string; modified: string } {
  const lines = diffText.split('\n');
  let original = '';
  let modified = '';

  // Process each line to build original and modified content
  for (const line of lines) {
    // Headers and context lines (ignore diff metadata)
    if (line.startsWith('diff ') || line.startsWith('index ') || 
        line.startsWith('--- ') || line.startsWith('+++ ') ||
        line.startsWith('@@')) {
      continue;
    }
    
    // Remove the first character for original and modified
    if (line.startsWith('-')) {
      original += line.substring(1) + '\n';
    } else if (line.startsWith('+')) {
      modified += line.substring(1) + '\n';
    } else {
      // Context lines go to both
      original += line + '\n';
      modified += line + '\n';
    }
  }
  
  return { original, modified };
}

// Function to format diff code with syntax highlighting
function formatDiffCode(code: string): string {
  // Split the code into lines
  const lines = code.split('\n');
  let lineNumber = 0;
  let inDiffHeader = false;
  
  const formattedLines = lines.map(line => {
    // Skip empty lines
    if (!line.trim()) {
      return `<span class="text-gray-400">${line}</span>`;
    }
    
    // Handle diff header lines (diff --git, index, +++ etc.)
    if (line.startsWith('diff ') || line.startsWith('index ') || 
        line.startsWith('--- ') || line.startsWith('+++ ') ||
        line.startsWith('@@')) {
      inDiffHeader = line.startsWith('@@');
      return `<span class="text-purple-600 dark:text-purple-400 font-semibold">${line}</span>`;
    }
    
    // Regular line numbering for non-header lines
    if (!inDiffHeader) {
      lineNumber++;
    }
    
    // Format based on line type
    if (line.startsWith('+')) {
      return `<span class="text-green-600 dark:text-green-400 font-bold"><span class="text-gray-400 mr-1 select-none w-6 inline-block text-right">${lineNumber}</span>${line}</span>`;
    } else if (line.startsWith('-')) {
      return `<span class="text-red-600 dark:text-red-400 font-bold"><span class="text-gray-400 mr-1 select-none w-6 inline-block text-right">${lineNumber}</span>${line}</span>`;
    } else {
      return `<span><span class="text-gray-400 mr-1 select-none w-6 inline-block text-right">${lineNumber}</span>${line}</span>`;
    }
  });
  
  return formattedLines.join('\n');
}

export default function Home() {
  // User state
  const [user, setUser] = useState<User | null>(null);
  const [userName, setUserName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [registerError, setRegisterError] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);

  // Bug state
  const [bugs, setBugs] = useState<Bug[]>([]);
  const [currentBug, setCurrentBug] = useState<Bug | null>(null);
  const [responses, setResponses] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showResults, setShowResults] = useState(false);
  const [totalAnswered, setTotalAnswered] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // For measuring response time
  const [startTime, setStartTime] = useState<number | null>(null);

  // Check for existing user session
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        localStorage.removeItem('user');
      }
    }
  }, []);

  // Fetch the bugs data from our API once the user is set
  useEffect(() => {
    if (!user) return;

    const fetchBugs = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/bugs?count=10&userId=${user.id}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch bugs: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        setBugs(data.bugs);
        
        if (data.bugs.length > 0) {
          pickRandomBug(data.bugs);
          setStartTime(Date.now()); // Start the timer for the first bug
        } else {
          setError("No bugs available. Please check the data files.");
        }
        
        setLoading(false);
      } catch (error) {
        console.error("Error fetching bugs:", error);
        setError("Failed to load bug data. Please try again later.");
        setLoading(false);
      }
    };

    fetchBugs();
  }, [user]);

  // Fetch previous responses for this user
  useEffect(() => {
    if (!user) return;

    const fetchPreviousResponses = async () => {
      try {
        const response = await fetch(`/api/responses?userId=${user.id}`);
        
        if (response.ok) {
          const data = await response.json();
          if (data.responses && Array.isArray(data.responses)) {
            // Convert the stored responses to our local format
            const previousResponses = data.responses.map((r: any) => ({
              bug_id: r.bug_id,
              actual_type: r.actual_type,
              user_response: r.user_response,
              correct: r.correct,
              response_time: r.response_time
            }));
            
            setResponses(previousResponses);
            setTotalAnswered(previousResponses.length);
          }
        }
      } catch (error) {
        console.error("Error fetching previous responses:", error);
      }
    };

    fetchPreviousResponses();
  }, [user]);

  const registerUser = async () => {
    if (!userName.trim() || !userEmail.trim()) {
      setRegisterError("Please provide both name and email");
      return;
    }

    setIsRegistering(true);
    setRegisterError("");

    try {
      const response = await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: userName.trim(),
          email: userEmail.trim()
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Registration failed');
      }

      const userData = await response.json();
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
    } catch (error) {
      console.error("Error registering user:", error);
      setRegisterError(error instanceof Error ? error.message : "Registration failed");
    } finally {
      setIsRegistering(false);
    }
  };

  const logoutUser = () => {
    setUser(null);
    localStorage.removeItem('user');
    setResponses([]);
    setTotalAnswered(0);
    setShowResults(false);
  };

  const pickRandomBug = (bugsList: Bug[]) => {
    if (bugsList.length > 0) {
      const randomIndex = Math.floor(Math.random() * bugsList.length);
      setCurrentBug(bugsList[randomIndex]);
      setStartTime(Date.now()); // Start the timer for this bug
    }
  };

  const fetchMoreBugs = async () => {
    try {
      // Only fetch more if we're running low
      if (bugs.length <= 5 && user) {
        const response = await fetch(`/api/bugs?count=10&userId=${user.id}`);
        
        if (response.ok) {
          const data = await response.json();
          if (data.bugs && data.bugs.length > 0) {
            // Append new bugs to our existing ones
            setBugs(prevBugs => {
              // Filter out any duplicates by instance_id
              const existingIds = new Set(prevBugs.map(bug => bug.instance_id));
              const newBugs = data.bugs.filter((bug: Bug) => !existingIds.has(bug.instance_id));
              return [...prevBugs, ...newBugs];
            });
          }
        }
      }
    } catch (error) {
      console.error("Error fetching more bugs:", error);
      // Don't show error to user, just log it
    }
  };

  const handleResponse = async (response: BugType) => {
    if (!currentBug || !user || !startTime) return;

    const endTime = Date.now();
    const responseTime = endTime - startTime;

    const isCorrect = response === currentBug.type;
    
    const newResponse: UserResponse = {
      bug_id: currentBug.instance_id,
      actual_type: currentBug.type,
      user_response: response,
      correct: isCorrect,
      response_time: responseTime
    };

    // Save response locally
    setResponses([...responses, newResponse]);
    setTotalAnswered(totalAnswered + 1);

    // Mark this bug as seen on the server
    try {
      await fetch('/api/bugs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: user.id,
          bugId: currentBug.instance_id
        })
      });
    } catch (error) {
      console.error("Error marking bug as seen:", error);
    }

    // Save response to server
    try {
      await fetch('/api/responses', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userId: user.id,
          userName: user.name,
          userEmail: user.email,
          bugId: currentBug.instance_id,
          actualType: currentBug.type,
          userResponse: response,
          responseTime: responseTime
        }),
      });
    } catch (error) {
      console.error("Error saving response:", error);
    }

    // Remove the current bug from the list
    const updatedBugs = bugs.filter(bug => bug.instance_id !== currentBug.instance_id);
    setBugs(updatedBugs);
    
    // Fetch more bugs if we're running low
    await fetchMoreBugs();

    // Pick another random bug
    if (updatedBugs.length > 0) {
      pickRandomBug(updatedBugs);
    } else {
      setError("No more bugs available. Please try again later.");
    }
  };

  const showFinalResults = () => {
    setShowResults(true);
  };

  const calculateResults = () => {
    const totalTrials = responses.length;
    const correctCount = responses.filter(r => r.correct).length;
    const proportion = correctCount / totalTrials;
    
    // Using Wilson score interval for confidence interval calculation
    // This is more accurate for small sample sizes than the normal approximation
    const z = 1.96; // 95% confidence
    const p = proportion;
    const n = totalTrials;
    
    const denominator = 1 + z*z/n;
    const centre = (p + z*z/(2*n)) / denominator;
    const interval = z * Math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator;
    
    const confidenceIntervalLow = Math.max(0, centre - interval);
    const confidenceIntervalHigh = Math.min(1, centre + interval);
    
    // Calculate p-value using binomial test approximation
    // H0: p = 0.5 (random guessing)
    // Two-sided test
    const standardError = Math.sqrt(0.5 * 0.5 / n);
    const zScore = Math.abs((p - 0.5) / standardError);
    
    // Convert z-score to p-value (approximation)
    const pValue = 2 * (1 - Math.min(
      0.9999, 
      0.5 * (1 + erf(zScore / Math.sqrt(2)))
    ));
    
    // Calculate accuracy for synthetic vs real bugs
    const syntheticResponses = responses.filter(r => r.actual_type === 'synthetic');
    const syntheticCorrect = syntheticResponses.filter(r => r.correct).length;
    const syntheticAccuracy = syntheticResponses.length > 0 
      ? syntheticCorrect / syntheticResponses.length 
      : 0;
    
    const realResponses = responses.filter(r => r.actual_type === 'real');
    const realCorrect = realResponses.filter(r => r.correct).length;
    const realAccuracy = realResponses.length > 0 
      ? realCorrect / realResponses.length 
      : 0;
    
    return {
      totalTrials,
      correctCount,
      proportion,
      confidenceIntervalLow,
      confidenceIntervalHigh,
      pValue,
      syntheticAccuracy,
      realAccuracy
    };
  };

  const resetExperiment = () => {
    setShowResults(false);
    pickRandomBug(bugs);
  };

  const handleSkip = async () => {
    if (!bugs.length || !user) return;
    
    // Mark this bug as seen on the server if it exists
    if (currentBug) {
      try {
        await fetch('/api/bugs', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            userId: user.id,
            bugId: currentBug.instance_id
          })
        });
      } catch (error) {
        console.error("Error marking skipped bug as seen:", error);
      }
      
      // Remove the current bug from the list
      const updatedBugs = bugs.filter(bug => bug.instance_id !== currentBug.instance_id);
      setBugs(updatedBugs);
      
      // Fetch more bugs if we're running low
      await fetchMoreBugs();
      
      // Pick another random bug
      if (updatedBugs.length > 0) {
        pickRandomBug(updatedBugs);
      } else {
        setError("No more bugs available. Please try again later.");
      }
    } else {
      // If no current bug, just pick a random one
      pickRandomBug(bugs);
    }
  };

  // User registration screen
  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <h1 className="text-2xl font-bold mb-6 text-center">Bug Classification Study</h1>
          
          <p className="mb-6 text-center">
            Please register to participate in our study on bug classification. We synthesized 10k bugs using target-based repo-level pipeline. But do they look like real bugs? Let's find out!
          </p>
          
          <div className="mb-4">
            <label htmlFor="name" className="block text-sm font-medium mb-1">
              Name
            </label>
            <input
              id="name"
              type="text"
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600"
              placeholder="Enter your name"
            />
          </div>
          
          <div className="mb-6">
            <label htmlFor="email" className="block text-sm font-medium mb-1">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={userEmail}
              onChange={(e) => setUserEmail(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600"
              placeholder="Enter your email"
            />
          </div>
          
          {registerError && (
            <div className="mb-4 text-red-500 text-center">
              {registerError}
            </div>
          )}
          
          <button
            onClick={registerUser}
            disabled={isRegistering}
            className="w-full bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 text-white font-semibold py-2 px-4 rounded-lg"
          >
            {isRegistering ? 'Registering...' : 'Register'}
          </button>
        </div>
      </div>
    );
  }

  // If results are being shown, display the statistics
  if (showResults) {
    const results = calculateResults();
    
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-2xl w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 mb-8">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold">Experiment Results</h1>
            <div>
              <span className="text-sm text-gray-500">
                Logged in as: <strong>{user.name}</strong>
              </span>
              <button 
                onClick={logoutUser}
                className="ml-4 text-sm text-red-500 hover:text-red-700"
              >
                Logout
              </button>
            </div>
          </div>
          
          <div className="mb-6">
            <p className="text-lg mb-2"><strong>Total trials:</strong> {results.totalTrials}</p>
            <p className="text-lg mb-2"><strong>Correct classifications:</strong> {results.correctCount}</p>
            <p className="text-lg mb-2"><strong>Proportion correct:</strong> {(results.proportion * 100).toFixed(1)}%</p>
            <p className="text-lg mb-2">
              <strong>95% Confidence Interval:</strong> 
              ({(results.confidenceIntervalLow * 100).toFixed(1)}%, {(results.confidenceIntervalHigh * 100).toFixed(1)}%)
            </p>
            <p className="text-lg mb-2">
              <strong>P-value (vs. random guessing):</strong> {results.pValue.toFixed(4)}
            </p>
            <p className="text-lg mb-2">
              <strong>Synthetic bug classification accuracy:</strong> {(results.syntheticAccuracy * 100).toFixed(1)}%
            </p>
            <p className="text-lg mb-2">
              <strong>Real bug classification accuracy:</strong> {(results.realAccuracy * 100).toFixed(1)}%
            </p>
            
            <div className="mt-6 p-4 bg-gray-100 dark:bg-gray-900 rounded-lg">
              <p className="text-sm">
                <strong>Interpretation:</strong> {results.pValue < 0.05 ? 
                  `The results show a statistically significant difference from random guessing (p < 0.05).` : 
                  `The results do not show a statistically significant difference from random guessing (p > 0.05).`}
              </p>
              <p className="text-sm mt-2">
                {results.proportion > 0.5 ? 
                  `You were able to distinguish between synthetic and real bugs beyond chance level.` : 
                  `You were not able to reliably distinguish between synthetic and real bugs.`}
              </p>
            </div>
          </div>

          <div className="text-center">
            <button
              onClick={resetExperiment}
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-6 rounded-lg"
            >
              Continue Classifying
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen py-3 px-2 md:p-4">
      <div className="w-[98%] max-w-[1800px] bg-white dark:bg-gray-800 shadow-lg rounded-lg p-5 md:p-8 lg:p-10 mb-4 bug-card">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center mb-6 md:mb-8">
          <h1 className="text-xl md:text-2xl font-bold mb-3 sm:mb-0 text-center sm:text-left">Bug Classification Study</h1>
          <div className="text-center sm:text-right flex items-center">
            <div className="flex flex-col items-end">
              <p className="text-sm text-gray-500 mr-4">Bugs classified: <strong>{totalAnswered}</strong></p>
              {totalAnswered < 30 && (
                <p className="text-xs text-blue-500 mr-4">🤗 Please classify 30 bugs to see your results!</p>
              )}
            </div>
            {totalAnswered >= 30 && (
              <button
                onClick={showFinalResults}
                className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-1 px-4 rounded-lg shadow-md text-sm mr-3"
              >
                Show Results
              </button>
            )}
            <span className="text-sm text-gray-500">
              Logged in as: <strong>{user.name}</strong>
            </span>
            <button 
              onClick={logoutUser}
              className="ml-4 text-sm text-red-500 hover:text-red-700"
            >
              Logout
            </button>
          </div>
        </div>
        
        {loading ? (
          <div className="text-center py-20">
            <p className="text-base">Loading bugs...</p>
          </div>
        ) : error ? (
          <div className="text-center py-20 text-red-500">
            <p className="text-base">{error}</p>
          </div>
        ) : (
          <>
            <p className="mb-6 md:mb-8 text-base">
              <strong>Instructions:</strong> Examine the code below and determine if the bug is synthetic 
              (artificially created) or from a real-world application. Red and white part and is the buggy code. Green part is the fix. We also provided a synthetic bug description to help you easier to make a decision.
            </p>
            
            <div className="mb-4 flex justify-between items-center">
              {/* Instance ID removed as requested */}
            </div>
            
            {/* Issue Description Section - Styled like GitHub Issue */}
            {currentBug?.issue_description && (
              <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
                {/* Issue header with avatar and info */}
                <div className="flex items-center px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                  <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center mr-2 text-white font-medium text-sm">
                    <span>B</span>
                  </div>
                  <span className="font-medium text-sm">BugReporter</span>
                  <span className="text-gray-500 text-xs ml-2">opened this issue</span>
                </div>
                
                {/* Issue content */}
                <div className="p-5 overflow-auto max-h-[400px]">
                  <div className="github-markdown">
                    {(() => {
                      try {
                        // First attempt - try to parse with our rich formatting
                        const formattedHtml = currentBug.issue_description
                          // Handle title format
                          .replace(/^Title: (.*)$/m, '<h1 class="text-2xl font-semibold mt-0 mb-4">$1</h1>')
                          .replace(/^Description:$/m, '')
                          // Handle markdown headings
                          .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-semibold mt-3 mb-3">$1</h1>')
                          .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold mt-4 mb-2">$1</h2>')
                          .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold mt-3 mb-2">$1</h3>')
                          // Handle section headers but preserve them as headers
                          .replace(/^(Issue Description:|Expected Behavior:|Environment:|Steps to Reproduce:|Actual Result:|Suggested Solution:)(.*)$/gm, 
                            '<h3 class="text-lg font-semibold mt-4 mb-2">$1$2</h3>')
                          // Format code blocks
                          .replace(/```(\w*)\n([\s\S]*?)\n```/g, 
                            '<pre class="bg-gray-50 dark:bg-gray-900 p-3 rounded my-3 overflow-auto text-sm font-mono"><code>$2</code></pre>')
                          // Format inline code with special handling for code elements
                          .replace(/`([^`]+)`/g, (match, code) => {
                            try {
                              // Special handling for inline code that looks like class names or constants
                              if (code.match(/^[A-Z][A-Za-z0-9_]*$/)) {
                                return `<code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-purple-600 dark:text-purple-400 text-sm">${code}</code>`;
                              } 
                              // Special handling for method/function names
                              else if (code.match(/^[a-z][A-Za-z0-9_]*\(?/)) {
                                return `<code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-blue-600 dark:text-blue-400 text-sm">${code}</code>`;
                              } 
                              // Default handling for other code
                              else {
                                return `<code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-red-600 dark:text-red-400 text-sm">${code}</code>`;
                              }
                            } catch (e) {
                              // If specific code formatting fails, use a safe default
                              return `<code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-gray-600 dark:text-gray-400 text-sm">${code}</code>`;
                            }
                          })
                          // Format lists
                          .replace(/^(\s*)- (.*)$/gm, 
                            '<div class="ml-5 flex mb-1"><span class="mr-2">•</span><span>$2</span></div>')
                          .replace(/^(\s*)(\d+)\. (.*)$/gm, 
                            '<div class="ml-3 flex mb-1"><span class="mr-2 font-medium">$2.</span><span>$3</span></div>')
                          // Format paragraphs - safer approach that won't match HTML tags
                          .replace(/^(?!<[h|p|d|c|p|s][a-z>])[^\n<].+$/gm, '<p class="my-2">$&</p>')
                          // Clean up extra paragraphs
                          .replace(/<\/p>\s*<p/g, '</p><p');
                          
                        return <div dangerouslySetInnerHTML={{ __html: formattedHtml }} />;
                      } catch (error) {
                        // Fallback method if rich parsing fails
                        try {
                          console.error("Error in rich markdown parsing:", error);
                          // Basic fallback parsing with minimal formatting
                          const basicHtml = currentBug.issue_description
                            .replace(/</g, '&lt;')
                            .replace(/>/g, '&gt;')
                            .replace(/\n\n/g, '<br /><br />')
                            .replace(/\n/g, '<br />');
                          
                          return (
                            <>
                              <div dangerouslySetInnerHTML={{ __html: basicHtml }} />
                              <div className="mt-4 p-2 bg-yellow-50 text-yellow-800 rounded text-sm">
                                Note: Using simplified formatting due to parsing issues.
                              </div>
                            </>
                          );
                        } catch (fallbackError) {
                          // Ultimate fallback if even basic parsing fails
                          console.error("Error in fallback parsing:", fallbackError);
                          return (
                            <div className="p-4 text-red-500 border border-red-200 rounded">
                              <p>Could not parse the issue description. Displaying raw content:</p>
                              <pre className="mt-2 p-2 bg-gray-50 dark:bg-gray-900 rounded overflow-auto">
                                {currentBug.issue_description}
                              </pre>
                            </div>
                          );
                        }
                      }
                    })()}
                  </div>
                </div>
              </div>
            )}
            
            <div className="flex flex-col md:flex-row gap-6 md:gap-8 mb-8 md:mb-10 flex-grow">
              {/* Left column: Error log trace */}
              <div className="w-full md:w-1/2 bg-gray-50 dark:bg-gray-900 p-4 md:p-5 rounded-lg shadow-sm trace-container">
                <h2 className="text-base font-semibold mb-4 pb-3 border-b border-gray-200 dark:border-gray-700">Error Log Trace</h2>
                <div className="font-mono text-xs overflow-auto h-[450px] md:h-[570px] lg:h-[550px] whitespace-pre-wrap text-gray-700 dark:text-gray-300 p-4">
                  {currentBug?.problem_statement}
                </div>
              </div>
              
              {/* Right column: Code with diff highlighting using Monaco editor */}
              <div className="w-full md:w-1/2 bg-gray-50 dark:bg-gray-900 p-4 md:p-5 rounded-lg shadow-sm code-container">
                <h2 className="text-base font-semibold mb-4 pb-3 border-b border-gray-200 dark:border-gray-700">Code with Bug</h2>
                {currentBug?.model_patch ? (
                  <div className="h-[450px] md:h-[570px] lg:h-[550px] overflow-hidden">
                    <DiffEditor
                      height="100%"
                      language="typescript" // Automatically detect language in a production app
                      original={extractDiffContent(currentBug.model_patch).original}
                      modified={extractDiffContent(currentBug.model_patch).modified}
                      theme={typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'vs-dark' : 'light'}
                      options={{
                        renderSideBySide: false, // Inline diff
                        readOnly: true,
                        minimap: { enabled: false },
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        diffWordWrap: 'on',
                        fontSize: 13,
                        hideUnchangedRegions: { enabled: true }
                      }}
                    />
                  </div>
                ) : (
                  <div className="font-mono text-xs h-[450px] md:h-[570px] lg:h-[550px] flex items-center justify-center text-gray-500">
                    No code diff available
                  </div>
                )}
              </div>
            </div>

            <p className="mb-8 text-center text-base font-semibold">Is this bug synthetic or real?</p>
            
            <div className="flex justify-center gap-4 md:gap-6 mb-6">
              <button
                onClick={() => handleResponse("synthetic")}
                className="bg-purple-500 hover:bg-purple-600 text-white font-semibold py-3 px-6 md:px-8 rounded-lg text-sm shadow-md classification-button"
              >
                Synthetic
              </button>
              <button
                onClick={() => handleResponse("real")}
                className="bg-green-500 hover:bg-green-600 text-white font-semibold py-3 px-6 md:px-8 rounded-lg text-sm shadow-md classification-button"
              >
                Real
              </button>
              <button
                onClick={handleSkip}
                className="bg-gray-400 hover:bg-gray-500 text-white font-semibold py-3 px-6 md:px-8 rounded-lg text-sm shadow-md classification-button"
              >
                Try Another Example
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
