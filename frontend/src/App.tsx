import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';

// Screen 1 through Screen 12 Pages
import { PortfolioStartPage } from './pages/PortfolioStartPage';
import { RepositoryDiscoveryPage } from './pages/RepositoryDiscoveryPage';
import { AddJobPage } from './pages/AddJobPage';
import { ReviewJobRequirementsPage } from './pages/ReviewJobRequirementsPage';
import { RepositoryScanStatusPage } from './pages/RepositoryScanStatusPage';
import { PortfolioSkillMapPage } from './pages/PortfolioSkillMapPage';
import { SkillGapAssessmentPage } from './pages/SkillGapAssessmentPage';
import { EvidenceDetailsPage } from './pages/EvidenceDetailsPage';
import { ChangeActivityWebhookPage } from './pages/ChangeActivityWebhookPage';
import { AssessmentHistoryPage } from './pages/AssessmentHistoryPage';
import { EvidenceComparisonPage } from './pages/EvidenceComparisonPage';
import { SettingsPage } from './pages/SettingsPage';

function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          {/* Screen 1: GitHub Portfolio Start */}
          <Route path="/" element={<PortfolioStartPage />} />
          
          {/* Screen 2: Repository Discovery & Scope Selection */}
          <Route path="/repositories" element={<RepositoryDiscoveryPage />} />

          {/* Screen 3: Add Target Job (URL or Paste) */}
          <Route path="/jobs/new" element={<AddJobPage />} />

          {/* Screen 4: Review Extracted Job Requirements */}
          <Route path="/jobs/review" element={<ReviewJobRequirementsPage />} />

          {/* Screen 5: Repository Scan Status & Telemetry */}
          <Route path="/scans/status" element={<RepositoryScanStatusPage />} />

          {/* Screen 6: Portfolio Skill Map */}
          <Route path="/skills" element={<PortfolioSkillMapPage />} />

          {/* Screen 7: Job-Specific Skill-Gap Assessment */}
          <Route path="/assessment" element={<SkillGapAssessmentPage />} />

          {/* Screen 8: Repository Evidence Details & Code Lines */}
          <Route path="/evidence" element={<EvidenceDetailsPage />} />

          {/* Screen 9: GitHub Change Activity & Webhook Status */}
          <Route path="/activity" element={<ChangeActivityWebhookPage />} />

          {/* Screen 10: Chronological Assessment History Ledger */}
          <Route path="/history" element={<AssessmentHistoryPage />} />

          {/* Screen 11: Requirement / Evidence Comparison Matrix */}
          <Route path="/comparison" element={<EvidenceComparisonPage />} />

          {/* Screen 12: Workspace & Integration Settings */}
          <Route path="/settings" element={<SettingsPage />} />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

export default App;
