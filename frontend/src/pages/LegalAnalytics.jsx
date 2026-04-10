import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCompany } from '../contexts/CompanyContext'

import DocumentUpload from '../components/legal/DocumentUpload'
import FacilityTerms from '../components/legal/FacilityTerms'
import EligibilityView from '../components/legal/EligibilityView'
import CovenantComparison from '../components/legal/CovenantComparison'
import EventsOfDefault from '../components/legal/EventsOfDefault'
import ReportingCalendar from '../components/legal/ReportingCalendar'
import RiskAssessment from '../components/legal/RiskAssessment'
import AmendmentHistory from '../components/legal/AmendmentHistory'

const TAB_MAP = {
  'documents':         DocumentUpload,
  'facility-terms':    FacilityTerms,
  'eligibility':       EligibilityView,
  'covenants-legal':   CovenantComparison,
  'events-of-default': EventsOfDefault,
  'reporting':         ReportingCalendar,
  'risk-assessment':   RiskAssessment,
  'amendments':        AmendmentHistory,
}

const fadeSlide = {
  initial: { opacity: 0, y: 12, filter: 'blur(3px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] } },
  exit:    { opacity: 0, filter: 'blur(3px)', transition: { duration: 0.15 } },
}

export default function LegalAnalytics() {
  const { tab } = useParams()
  const { company, product, snapshot, currency, asOfDate } = useCompany()

  const TabComponent = TAB_MAP[tab] || DocumentUpload

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{
          fontSize: 18,
          fontWeight: 700,
          color: 'var(--text-primary)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--gold)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          Legal Analysis
        </h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>
          AI-powered facility agreement analysis and compliance monitoring
        </p>
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div key={tab} {...fadeSlide}>
          <TabComponent
            company={company}
            product={product}
            snapshot={snapshot}
            currency={currency}
            asOfDate={asOfDate}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
