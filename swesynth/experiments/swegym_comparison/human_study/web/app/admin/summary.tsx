"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Bar, Pie } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from "chart.js";

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

interface AggregateStats {
  totalUsers: number;
  totalResponses: number;
  overallAccuracy: number;
  syntheticAccuracy: number;
  realAccuracy: number;
  averageResponseTime: number;
  significantUsers: number;
  usersAboveChance: number;
  userStats: UserStat[];
  responseDistribution: {
    syntheticCorrect: number;
    syntheticIncorrect: number;
    realCorrect: number;
    realIncorrect: number;
  };
}

interface UserStat {
  userId: string;
  userName: string;
  email: string;
  totalResponses: number;
  accuracy: number;
  syntheticAccuracy: number;
  realAccuracy: number;
  pValue: number;
}

export default function AdminSummary() {
  const [stats, setStats] = useState<AggregateStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<{id: string, name: string, email: string} | null>(null);
  const [isAuthorized, setIsAuthorized] = useState(false);
  
  // Check if current user is authorized
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      try {
        const userData = JSON.parse(storedUser);
        setUser(userData);
        
        // Check if the user is the authorized admin
        if (userData.email === "...@gmail.com") {
          setIsAuthorized(true);
          fetchSummaryData();
        } else {
          setError("You are not authorized to view this page.");
          setLoading(false);
        }
      } catch (e) {
        setError("Error loading user data.");
        setLoading(false);
      }
    } else {
      setError("Please log in to access this page.");
      setLoading(false);
    }
  }, []);

  const fetchSummaryData = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/admin/summary');
      
      if (!response.ok) {
        throw new Error(`Failed to fetch summary data: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      setStats(data.stats);
      setLoading(false);
    } catch (error) {
      console.error("Error fetching summary data:", error);
      setError("Failed to load summary data. Please try again later.");
      setLoading(false);
    }
  };

  if (!isAuthorized && !loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <h1 className="text-2xl font-bold mb-6 text-center">Access Denied</h1>
          <p className="mb-6 text-center text-red-500">
            {error || "You don't have permission to view this page."}
          </p>
          <div className="text-center">
            <Link 
              href="/"
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg"
            >
              Return to Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 text-center">
          <h1 className="text-2xl font-bold mb-6">Summary Dashboard</h1>
          <p className="mb-6">Loading summary data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-8">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <h1 className="text-2xl font-bold mb-6 text-center">Error</h1>
          <p className="mb-6 text-center text-red-500">{error}</p>
          <div className="text-center">
            <button 
              onClick={fetchSummaryData}
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 px-4 rounded-lg"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Charts data for accuracy comparison
  const accuracyData = {
    labels: ['Overall', 'Synthetic Bugs', 'Real Bugs'],
    datasets: [
      {
        label: 'Accuracy (%)',
        data: [
          (stats?.overallAccuracy || 0) * 100,
          (stats?.syntheticAccuracy || 0) * 100,
          (stats?.realAccuracy || 0) * 100
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.6)',
          'rgba(153, 102, 255, 0.6)',
          'rgba(75, 192, 192, 0.6)'
        ],
        borderColor: [
          'rgba(54, 162, 235, 1)',
          'rgba(153, 102, 255, 1)',
          'rgba(75, 192, 192, 1)'
        ],
        borderWidth: 1,
      }
    ]
  };

  // Pie chart for confusion matrix
  const confusionData = {
    labels: [
      'Synthetic Correct', 
      'Synthetic Incorrect', 
      'Real Correct', 
      'Real Incorrect'
    ],
    datasets: [
      {
        data: [
          stats?.responseDistribution.syntheticCorrect || 0,
          stats?.responseDistribution.syntheticIncorrect || 0,
          stats?.responseDistribution.realCorrect || 0,
          stats?.responseDistribution.realIncorrect || 0,
        ],
        backgroundColor: [
          'rgba(153, 102, 255, 0.6)',
          'rgba(255, 99, 132, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(255, 159, 64, 0.6)'
        ],
        borderColor: [
          'rgba(153, 102, 255, 1)',
          'rgba(255, 99, 132, 1)',
          'rgba(75, 192, 192, 1)',
          'rgba(255, 159, 64, 1)'
        ],
        borderWidth: 1,
      }
    ]
  };

  // Generate insights and conclusions based on the data
  const generateInsights = () => {
    const insights = [];
    
    // Check if users can distinguish between synthetic and real bugs
    if (stats?.overallAccuracy && stats.overallAccuracy > 0.55) {
      insights.push("Participants were able to distinguish between synthetic and real bugs above chance level.");
    } else {
      insights.push("Participants were not able to reliably distinguish between synthetic and real bugs.");
    }
    
    // Check if synthetic bugs are more recognizable
    if (stats?.syntheticAccuracy && stats?.realAccuracy) {
      if (stats.syntheticAccuracy > stats.realAccuracy + 0.05) {
        insights.push("Synthetic bugs were more easily identified than real bugs.");
      } else if (stats.realAccuracy > stats.syntheticAccuracy + 0.05) {
        insights.push("Real bugs were more easily identified than synthetic bugs.");
      } else {
        insights.push("Synthetic and real bugs were identified with similar accuracy.");
      }
    }
    
    // Statistical significance
    if (stats?.significantUsers && stats?.totalUsers) {
      const significantPercentage = (stats.significantUsers / stats.totalUsers) * 100;
      if (significantPercentage > 50) {
        insights.push(`${significantPercentage.toFixed(1)}% of participants showed statistically significant ability to distinguish between bug types (p < 0.05).`);
      } else {
        insights.push(`Only ${significantPercentage.toFixed(1)}% of participants showed statistically significant ability to distinguish between bug types.`);
      }
    }
    
    // Overall conclusion
    if (stats?.overallAccuracy) {
      if (stats.overallAccuracy > 0.6) {
        insights.push("CONCLUSION: Synthetic bugs appear distinguishable from real bugs, suggesting further refinement of generation methods may be needed.");
      } else if (stats.overallAccuracy < 0.55) {
        insights.push("CONCLUSION: Synthetic bugs appear indistinguishable from real bugs, suggesting high quality of the generation pipeline.");
      } else {
        insights.push("CONCLUSION: Results are inconclusive - participants show marginal ability to distinguish synthetic from real bugs.");
      }
    }
    
    return insights;
  };

  return (
    <div className="flex flex-col min-h-screen p-6">
      <div className="max-w-6xl w-full mx-auto bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8 mb-8">
        <div className="flex justify-between items-center mb-8 border-b border-gray-200 dark:border-gray-700 pb-4">
          <h1 className="text-2xl font-bold">Bug Classification Study: Aggregate Results</h1>
          <div className="flex items-center">
            <span className="text-sm text-gray-500 mr-4">
              Admin: <strong>{user?.name}</strong>
            </span>
            <Link 
              href="/"
              className="bg-blue-500 hover:bg-blue-600 text-white font-semibold py-1 px-3 rounded text-sm"
            >
              Return to Study
            </Link>
          </div>
        </div>

        {/* Key Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
            <h3 className="text-sm font-medium text-blue-600 dark:text-blue-400">Total Participants</h3>
            <p className="text-3xl font-bold text-blue-800 dark:text-blue-300">{stats?.totalUsers || 0}</p>
          </div>
          <div className="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg">
            <h3 className="text-sm font-medium text-purple-600 dark:text-purple-400">Total Classifications</h3>
            <p className="text-3xl font-bold text-purple-800 dark:text-purple-300">{stats?.totalResponses || 0}</p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
            <h3 className="text-sm font-medium text-green-600 dark:text-green-400">Overall Accuracy</h3>
            <p className="text-3xl font-bold text-green-800 dark:text-green-300">{((stats?.overallAccuracy || 0) * 100).toFixed(1)}%</p>
          </div>
          <div className="bg-orange-50 dark:bg-orange-900/20 p-4 rounded-lg">
            <h3 className="text-sm font-medium text-orange-600 dark:text-orange-400">Avg Response Time</h3>
            <p className="text-3xl font-bold text-orange-800 dark:text-orange-300">{((stats?.averageResponseTime || 0) / 1000).toFixed(1)}s</p>
          </div>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
            <h3 className="text-base font-medium mb-4 text-center">Accuracy by Bug Type</h3>
            <div className="h-64">
              <Bar 
                data={accuracyData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: {
                    y: {
                      beginAtZero: true,
                      max: 100,
                      title: {
                        display: true,
                        text: 'Percentage (%)'
                      }
                    }
                  }
                }} 
              />
            </div>
          </div>
          <div className="bg-gray-50 dark:bg-gray-900 p-4 rounded-lg">
            <h3 className="text-base font-medium mb-4 text-center">Response Distribution</h3>
            <div className="h-64 flex items-center justify-center">
              <div className="w-3/4 h-full">
                <Pie 
                  data={confusionData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                  }} 
                />
              </div>
            </div>
          </div>
        </div>

        {/* Insights and Conclusions */}
        <div className="bg-gray-50 dark:bg-gray-900 p-6 rounded-lg mb-8">
          <h3 className="text-lg font-semibold mb-4">Key Insights and Conclusions</h3>
          <ul className="space-y-2">
            {generateInsights().map((insight, index) => (
              <li key={index} className={`py-2 ${insight.startsWith('CONCLUSION') ? 'font-bold border-t border-gray-200 dark:border-gray-700 pt-4 mt-4' : ''}`}>
                {insight}
              </li>
            ))}
          </ul>
        </div>

        {/* Top Performers */}
        <div className="bg-gray-50 dark:bg-gray-900 p-6 rounded-lg">
          <h3 className="text-lg font-semibold mb-4">Top Performers</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 dark:bg-gray-800">
                <tr>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Responses</th>
                  <th className="px-4 py-2 text-left">Overall Accuracy</th>
                  <th className="px-4 py-2 text-left">Synthetic Accuracy</th>
                  <th className="px-4 py-2 text-left">Real Accuracy</th>
                  <th className="px-4 py-2 text-left">P-Value</th>
                </tr>
              </thead>
              <tbody>
                {stats?.userStats
                  .sort((a, b) => b.accuracy - a.accuracy)
                  .slice(0, 10)
                  .map((user, index) => (
                    <tr key={index} className="border-b border-gray-200 dark:border-gray-700">
                      <td className="px-4 py-2">{user.userName}</td>
                      <td className="px-4 py-2">{user.totalResponses}</td>
                      <td className="px-4 py-2">{(user.accuracy * 100).toFixed(1)}%</td>
                      <td className="px-4 py-2">{(user.syntheticAccuracy * 100).toFixed(1)}%</td>
                      <td className="px-4 py-2">{(user.realAccuracy * 100).toFixed(1)}%</td>
                      <td className="px-4 py-2">{user.pValue < 0.05 ? 
                        <span className="text-green-500 font-semibold">{user.pValue.toFixed(4)}</span> : 
                        <span className="text-red-500">{user.pValue.toFixed(4)}</span>
                      }</td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
} 