"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface UserBreakdown {
  userId: string;
  userName: string;
  totalResponses: number;
  accuracy: number;
}

interface AnalysisResults {
  overallStats: {
    totalUsers: number;
    totalResponses: number;
    avgResponsesPerUser: number;
    overallAccuracy: number;
    syntheticAccuracy: number;
    realAccuracy: number;
    confusionMatrix: {
      truePositives: number;
      falsePositives: number;
      trueNegatives: number;
      falseNegatives: number;
    };
  };
  userBreakdown: UserBreakdown[];
  responseTimeStats: {
    avgResponseTime: number;
    medianResponseTime: number;
    minResponseTime: number;
    maxResponseTime: number;
  };
}

interface UserResults {
  user_id: string;
  user_name: string;
  user_email: string;
  responses: UserResponse[];
  summary?: {
    total_responses: number;
    correct_responses: number;
    accuracy: number;
    p_value: number;
    synthetic_accuracy: number;
    real_accuracy: number;
  };
}

interface UserResponse {
  user_id: string;
  bug_id: string;
  actual_type: 'synthetic' | 'real';
  user_response: 'synthetic' | 'real';
  correct: boolean;
  response_time: number;
  timestamp: string;
}

export default function AdminPage() {
  const [analysis, setAnalysis] = useState<AnalysisResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adminPassword, setAdminPassword] = useState("");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [userResults, setUserResults] = useState<UserResults | null>(null);
  const [loadingUserResults, setLoadingUserResults] = useState(false);
  
  const fetchAnalysis = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/analysis');
      
      if (!response.ok) {
        throw new Error(`Failed to fetch analysis: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      setAnalysis(data.data);
      setLoading(false);
    } catch (error) {
      console.error("Error fetching analysis:", error);
      setError("Failed to load analysis data");
      setLoading(false);
    }
  };
  
  const fetchUserResults = async (userId: string) => {
    setLoadingUserResults(true);
    try {
      const response = await fetch(`/api/responses?userId=${userId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch user results: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      setUserResults(data);
      setLoadingUserResults(false);
    } catch (error) {
      console.error("Error fetching user results:", error);
      setUserResults(null);
      setLoadingUserResults(false);
    }
  };
  
  const handleUserSelect = (userId: string) => {
    setSelectedUser(userId);
    fetchUserResults(userId);
  };
  
  const authenticate = () => {
    // In a real application, you would validate against a secure backend
    // This is a simple example password for demonstration purposes only
    if (adminPassword === "admin123") {
      setIsAuthenticated(true);
      fetchAnalysis();
    } else {
      setError("Invalid password");
    }
  };
  
  const downloadAllResponses = async () => {
    try {
      // Fetch all user results
      const allUserResults: UserResults[] = [];
      
      for (const user of analysis?.userBreakdown || []) {
        const response = await fetch(`/api/responses?userId=${user.userId}`);
        if (response.ok) {
          const data = await response.json();
          allUserResults.push(data);
        }
      }
      
      // Create a downloadable JSON file
      const dataStr = JSON.stringify(allUserResults, null, 2);
      const dataUri = `data:application/json;charset=utf-8,${encodeURIComponent(dataStr)}`;
      
      const exportFileName = `bug_classification_results_${new Date().toISOString().slice(0, 10)}.json`;
      
      const linkElement = document.createElement('a');
      linkElement.setAttribute('href', dataUri);
      linkElement.setAttribute('download', exportFileName);
      linkElement.click();
    } catch (error) {
      console.error("Error downloading responses:", error);
      setError("Failed to download responses");
    }
  };
  
  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <h1 className="text-2xl font-bold mb-6 text-center">Admin Dashboard</h1>
          
          <p className="mb-6 text-center">
            Please enter the admin password to access the analysis dashboard.
          </p>
          
          <div className="mb-6">
            <label htmlFor="password" className="block text-sm font-medium mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600"
              placeholder="Enter admin password"
            />
          </div>
          
          {error && (
            <div className="mb-4 text-red-500 text-center">
              {error}
            </div>
          )}
          
          <button
            onClick={authenticate}
            className="w-full bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg"
          >
            Login
          </button>
          
          <div className="mt-4 text-center">
            <Link 
              href="/"
              className="text-blue-500 hover:text-blue-700 text-sm"
            >
              Back to Experiment
            </Link>
          </div>
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex flex-col min-h-screen p-8">
      <div className="max-w-5xl w-full mx-auto bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 mb-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <div className="flex space-x-4">
            <Link 
              href="/admin/summary"
              className="bg-indigo-500 hover:bg-indigo-600 text-white font-semibold py-2 px-4 rounded-lg text-sm"
            >
              View Summary Dashboard
            </Link>
            <button
              onClick={downloadAllResponses}
              className="bg-green-500 hover:bg-green-600 text-white font-semibold py-2 px-4 rounded-lg text-sm"
            >
              Download All Data
            </button>
            <Link 
              href="/"
              className="bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 font-semibold py-2 px-4 rounded-lg text-sm"
            >
              Back to Experiment
            </Link>
          </div>
        </div>
        
        {loading ? (
          <div className="text-center py-8">
            <p>Loading analysis data...</p>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-500">
            <p>{error}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Overall Statistics */}
            <div className="col-span-2">
              <h2 className="text-xl font-semibold mb-4">Overall Statistics</h2>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Users</p>
                  <p className="text-2xl font-bold">{analysis?.overallStats.totalUsers}</p>
                </div>
                <div className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Responses</p>
                  <p className="text-2xl font-bold">{analysis?.overallStats.totalResponses}</p>
                </div>
                <div className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Overall Accuracy</p>
                  <p className="text-2xl font-bold">
                    {(analysis?.overallStats.overallAccuracy || 0) * 100}%
                  </p>
                </div>
                <div className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                  <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Avg. Responses Per User</p>
                  <p className="text-2xl font-bold">
                    {analysis?.overallStats.avgResponsesPerUser.toFixed(1)}
                  </p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-purple-100 dark:bg-purple-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-purple-500 dark:text-purple-400">Synthetic Accuracy</p>
                  <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">
                    {(analysis?.overallStats.syntheticAccuracy || 0) * 100}%
                  </p>
                </div>
                <div className="bg-green-100 dark:bg-green-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-green-500 dark:text-green-400">Real Accuracy</p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {(analysis?.overallStats.realAccuracy || 0) * 100}%
                  </p>
                </div>
              </div>
              
              <h3 className="text-lg font-semibold mb-3">Confusion Matrix</h3>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-green-100 dark:bg-green-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-green-500 dark:text-green-400">
                    True Positives (Synthetic correctly identified)
                  </p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {analysis?.overallStats.confusionMatrix.truePositives}
                  </p>
                </div>
                <div className="bg-red-100 dark:bg-red-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-red-500 dark:text-red-400">
                    False Positives (Real misidentified as Synthetic)
                  </p>
                  <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                    {analysis?.overallStats.confusionMatrix.falsePositives}
                  </p>
                </div>
                <div className="bg-red-100 dark:bg-red-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-red-500 dark:text-red-400">
                    False Negatives (Synthetic misidentified as Real)
                  </p>
                  <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                    {analysis?.overallStats.confusionMatrix.falseNegatives}
                  </p>
                </div>
                <div className="bg-green-100 dark:bg-green-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-green-500 dark:text-green-400">
                    True Negatives (Real correctly identified)
                  </p>
                  <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {analysis?.overallStats.confusionMatrix.trueNegatives}
                  </p>
                </div>
              </div>
              
              <h3 className="text-lg font-semibold mb-3">Response Time Statistics</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                <div className="bg-blue-100 dark:bg-blue-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-blue-500 dark:text-blue-400">
                    Average
                  </p>
                  <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                    {Math.round(analysis?.responseTimeStats.avgResponseTime || 0) / 1000}s
                  </p>
                </div>
                <div className="bg-blue-100 dark:bg-blue-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-blue-500 dark:text-blue-400">
                    Median
                  </p>
                  <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                    {Math.round(analysis?.responseTimeStats.medianResponseTime || 0) / 1000}s
                  </p>
                </div>
                <div className="bg-blue-100 dark:bg-blue-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-blue-500 dark:text-blue-400">
                    Minimum
                  </p>
                  <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                    {Math.round(analysis?.responseTimeStats.minResponseTime || 0) / 1000}s
                  </p>
                </div>
                <div className="bg-blue-100 dark:bg-blue-900/20 p-4 rounded-lg">
                  <p className="text-sm font-medium text-blue-500 dark:text-blue-400">
                    Maximum
                  </p>
                  <p className="text-xl font-bold text-blue-700 dark:text-blue-300">
                    {Math.round(analysis?.responseTimeStats.maxResponseTime || 0) / 1000}s
                  </p>
                </div>
              </div>
            </div>
            
            {/* User Breakdown */}
            <div>
              <h2 className="text-xl font-semibold mb-4">User Results</h2>
              <div className="mb-4 max-h-80 overflow-y-auto bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                {analysis?.userBreakdown.length === 0 ? (
                  <p className="text-gray-500 text-center py-4">No user data available</p>
                ) : (
                  <ul className="divide-y divide-gray-200 dark:divide-gray-700">
                    {analysis?.userBreakdown.map((user) => (
                      <li 
                        key={user.userId}
                        className={`py-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-800 ${
                          selectedUser === user.userId ? 'bg-gray-200 dark:bg-gray-800' : ''
                        }`}
                        onClick={() => handleUserSelect(user.userId)}
                      >
                        <p className="font-medium">{user.userName}</p>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-500">{user.totalResponses} responses</span>
                          <span className={user.accuracy >= 0.5 ? 'text-green-500' : 'text-red-500'}>
                            {(user.accuracy * 100).toFixed(1)}% accuracy
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              
              {/* Individual User Results */}
              {selectedUser && (
                <div className="bg-gray-100 dark:bg-gray-900 p-4 rounded-lg">
                  {loadingUserResults ? (
                    <p className="text-center py-2">Loading user results...</p>
                  ) : !userResults ? (
                    <p className="text-center py-2">Failed to load user results</p>
                  ) : (
                    <>
                      <h3 className="font-semibold mb-2">
                        {userResults.user_name}'s Results
                      </h3>
                      
                      {userResults.summary && (
                        <div className="mb-2">
                          <p className="text-sm">
                            <span className="text-gray-500">Accuracy:</span> {(userResults.summary.accuracy * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm">
                            <span className="text-gray-500">P-value:</span> {userResults.summary.p_value.toFixed(4)}
                          </p>
                          <p className="text-sm">
                            <span className="text-gray-500">Synthetic Accuracy:</span> {(userResults.summary.synthetic_accuracy * 100).toFixed(1)}%
                          </p>
                          <p className="text-sm">
                            <span className="text-gray-500">Real Accuracy:</span> {(userResults.summary.real_accuracy * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}
                      
                      <p className="text-xs text-gray-500 mt-2 mb-1">Recent responses:</p>
                      <div className="max-h-40 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-gray-300 dark:border-gray-700">
                              <th className="text-left py-1">Bug ID</th>
                              <th className="text-left py-1">Type</th>
                              <th className="text-left py-1">Response</th>
                              <th className="text-left py-1">Correct</th>
                            </tr>
                          </thead>
                          <tbody>
                            {userResults.responses.slice(-5).map((response, index) => (
                              <tr key={index} className="border-b border-gray-200 dark:border-gray-800">
                                <td className="py-1">{response.bug_id.slice(0, 6)}</td>
                                <td className="py-1">
                                  <span className={`${
                                    response.actual_type === 'synthetic' ? 'text-purple-500' : 'text-green-500'
                                  }`}>
                                    {response.actual_type}
                                  </span>
                                </td>
                                <td className="py-1">
                                  <span className={`${
                                    response.user_response === 'synthetic' ? 'text-purple-500' : 'text-green-500'
                                  }`}>
                                    {response.user_response}
                                  </span>
                                </td>
                                <td className="py-1">
                                  <span className={`${
                                    response.correct ? 'text-green-500' : 'text-red-500'
                                  }`}>
                                    {response.correct ? '✓' : '✗'}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
} 