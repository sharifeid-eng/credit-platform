import { useState, useEffect } from 'react'

const MOBILE  = '(max-width: 767px)'
const TABLET  = '(min-width: 768px) and (max-width: 1023px)'

export default function useBreakpoint() {
  const [state, setState] = useState(() => {
    if (typeof window === 'undefined') return { isMobile: false, isTablet: false, isDesktop: true }
    return {
      isMobile:  window.matchMedia(MOBILE).matches,
      isTablet:  window.matchMedia(TABLET).matches,
      isDesktop: window.matchMedia('(min-width: 1024px)').matches,
    }
  })

  useEffect(() => {
    const mql  = window.matchMedia(MOBILE)
    const tql  = window.matchMedia(TABLET)

    const update = () => setState({
      isMobile:  mql.matches,
      isTablet:  tql.matches,
      isDesktop: !mql.matches && !tql.matches,
    })

    mql.addEventListener('change', update)
    tql.addEventListener('change', update)
    return () => {
      mql.removeEventListener('change', update)
      tql.removeEventListener('change', update)
    }
  }, [])

  return state
}
