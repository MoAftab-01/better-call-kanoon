/**
 * The EN / HI (Devanagari) string table.
 *
 * Carried over verbatim from the original vanilla-JS prototype's `I18N`
 * object - every string it owned appears here with the same wording. Legal and
 * system data (disclaimer, starter questions, helplines) is never stored in
 * this file; it always comes from the backend, so the two can never drift
 * apart.
 *
 * The keys mirror `supported_languages` in `app/config.py`: `en` and `hi`.
 */

/**
 * The locales this build can render.
 *
 * Declared here, as an explicit union, rather than derived from `STRINGS` with
 * `keyof typeof STRINGS`. That derivation is circular — `STRINGS` is typed
 * `Record<LanguageCode, Strings>`, so `LanguageCode` would depend on `STRINGS`
 * while `STRINGS` depends on `LanguageCode` — and the compiler rejects it.
 * The string table is also where the locales actually live, so this is the
 * natural home for the type.
 */
export type LanguageCode = 'en' | 'hi'

/**
 * Narrow an arbitrary value to a locale this build can actually render.
 *
 * The one true test for renderability: `STRINGS` has exactly one table per
 * `LanguageCode` and no fallback table, so any code that is not in this union
 * resolves to `undefined` and throws on first read. The server's
 * `SUPPORTED_LANGUAGES` is an operator-editable comma-separated list with no
 * allowlist, so a code from the wire is untrusted and must be checked here
 * before it reaches the language state.
 *
 * Lives beside `LanguageCode` and `STRINGS` so the mappers and the language
 * hook can share one definition of "renderable" instead of each keeping its own.
 */
export function isLanguageCode(value: unknown): value is LanguageCode {
  return value === 'en' || value === 'hi'
}

/** Every key the UI can render. Adding one here forces both locales to supply it. */
export interface Strings {
  htmlLang: string
  skipToContent: string
  languageGroup: string
  statusChecking: string
  statusHealthy: string
  statusDown: string
  sectionStarter: string
  sectionAsk: string
  sectionVoice: string
  sectionMessages: string
  heroHeading: string
  heroSub: string
  composerPlaceholder: string
  composerSend: string
  composerEmpty: string
  composerTooLong: string
  composerTooLongSuffix: string
  composerPending: string
  micLabel: string
  micHint: string
  readAloud: string
  speechRate: string
  voiceHint: string
  voiceUnavailable: string
  emergencyBtn: string
  emergencyTitle: string
  emergencySub: string
  emergencyClose: string
  emergencyNone: string
  unverified: string
  unverifiedExplain: string
  callLabel: string
  retry: string
  configDown: string
  configLoading: string
  footerNote: string
  composerLabel: string
  stageNote: string
  dismissDisclaimer: string
  disclaimerHeading: string
  messagesEmpty: string
  userMessageLabel: string
  appMessageLabel: string
  listening: string
  speakAgain: string
  stopSpeaking: string
  statusBarUnavailable: string
  statusBarUnavailableBody: string
}

export const STRINGS: Record<LanguageCode, Strings> = {
  en: {
    htmlLang: 'en',
    skipToContent: 'Skip to main content',
    languageGroup: 'Language',
    statusChecking: 'Checking service…',
    statusHealthy: 'Service healthy',
    statusDown: 'Service unavailable',
    sectionStarter: 'Start with a common question',
    sectionAsk: 'Ask your question',
    sectionVoice: 'Voice settings',
    sectionMessages: 'Messages',
    heroHeading: 'How can I help you understand Indian law?',
    heroSub:
      'Ask about a law, a right, or what to do next. Information only — not legal advice.',
    composerPlaceholder: 'Type your question…',
    composerSend: 'Send',
    composerEmpty: 'Type a question first.',
    composerTooLong: 'Please keep your question under ',
    composerTooLongSuffix: ' characters.',
    composerPending:
      'Answer is being retrieved from legal sources — please wait.',
    micLabel: 'Tap to speak — voice input',
    micHint: 'Voice input arrives in a later stage. Use the keyboard for now.',
    readAloud: 'Read answers aloud',
    speechRate: 'Speech rate',
    voiceHint: 'Read-aloud is not active yet — it arrives with the answering stage.',
    voiceUnavailable:
      'Voice input is not available in this browser. You can still type your question.',
    emergencyBtn: 'Emergency Help',
    emergencyTitle: 'Emergency Help',
    emergencySub: 'Tapping a number dials it on this device.',
    emergencyClose: 'Close emergency help',
    emergencyNone: 'Emergency numbers could not be loaded.',
    unverified: 'Unverified',
    unverifiedExplain:
      'Not yet verified against an official Government of India source. Check the number before relying on it.',
    callLabel: 'Call',
    retry: 'Try again',
    configDown:
      'Cannot reach the server, so language options and emergency numbers could not be loaded. Some features are unavailable.',
    configLoading: 'Loading configuration…',
    footerNote: 'Information only — not a lawyer and not legal advice.',
    composerLabel: 'Type your legal question',
    stageNote:
      'Answering is live — retrieval and generation are active.',
    dismissDisclaimer: 'Dismiss disclaimer for this session',
    disclaimerHeading: 'Disclaimer',
    messagesEmpty: 'No messages yet.',
    userMessageLabel: 'You asked',
    appMessageLabel: 'Better Call Kanoon',
    listening: 'Listening…',
    speakAgain: 'Read aloud',
    stopSpeaking: 'Stop reading',
    statusBarUnavailable: 'Service unavailable',
    statusBarUnavailableBody:
      'The backend is not responding, so this page is showing limited information only.',
  },
  hi: {
    htmlLang: 'hi',
    skipToContent: 'मुख्य सामग्री पर जाएँ',
    languageGroup: 'भाषा',
    statusChecking: 'सेवा जाँच हो रही है…',
    statusHealthy: 'सेवा उपलब्ध है',
    statusDown: 'सेवा उपलब्ध नहीं है',
    sectionStarter: 'एक सामान्य प्रश्न से शुरू करें',
    sectionAsk: 'अपना प्रश्न पूछें',
    sectionVoice: 'आवाज़ सेटिंग्स',
    sectionMessages: 'संदेश',
    heroHeading: 'मैं भारतीय कानून को समझने में आपकी कैसे मदद कर सकती हूँ?',
    heroSub:
      'किसी कानून, अधिकार या आगे क्या करना है, इसके बारे में पूछें। केवल जानकारी — कानूनी सलाह नहीं।',
    composerPlaceholder: 'अपना प्रश्न लिखें…',
    composerSend: 'भेजें',
    composerEmpty: 'पहले कोई प्रश्न लिखें।',
    composerTooLong: 'कृपया अपना प्रश्न ',
    composerTooLongSuffix: ' अक्षरों से कम रखें।',
    composerPending:
      'अभी उत्तर देना उपलब्ध नहीं है। बैकएंड उत्तर सुविधा अगले चरण में आएगी, इसलिए कुछ भी नहीं भेजा गया है।',
    micLabel: 'बोलने के लिए टैप करें — आवाज़ से इनपुट',
    micHint: 'आवाज़ से इनपुट अगले चरण में आएगा। अभी कीबोर्ड का उपयोग करें।',
    readAloud: 'उत्तर सुनकर दिखाएँ',
    speechRate: 'बोलने की गति',
    voiceHint: 'सुनकर दिखाना अभी सक्रिय नहीं है — यह उत्तर वाले चरण में आएगा।',
    voiceUnavailable:
      'इस ब्राउज़र में आवाज़ से इनपुट उपलब्ध नहीं है। आप अपना प्रश्न लिख सकते हैं।',
    emergencyBtn: 'आपातकालीन सहायता',
    emergencyTitle: 'आपातकालीन सहायता',
    emergencySub: 'किसी नंबर पर टैप करने पर वह इस डिवाइस से डायल होगा।',
    emergencyClose: 'आपातकालीन सहायता बंद करें',
    emergencyNone: 'आपातकालीन नंबर लोड नहीं हो सके।',
    unverified: 'सत्यापित नहीं',
    unverifiedExplain:
      'भारत सरकार के आधिकारिक स्रोत से अभी सत्यापित नहीं किया गया। निर्भर रहने से पहले नंबर जाँच लें।',
    callLabel: 'कॉल करें',
    retry: 'फिर कोशिश करें',
    configDown:
      'सर्वर से संपर्क नहीं हो सका, इसलिए भाषा विकल्प और आपातकालीन नंबर लोड नहीं हो सके। कुछ सुविधाएँ उपलब्ध नहीं हैं।',
    configLoading: 'सेटअप लोड हो रहा है…',
    footerNote: 'केवल जानकारी — यह कानूनी सलाह नहीं है।',
    composerLabel: 'अपना कानूनी प्रश्न लिखें',
    stageNote:
      'चरण 1 — केवल इंटरफ़ेस। प्रश्नोत्तर, सूचना-खोज और आवाज़ इनपुट बनाया जा रहा है।',
    dismissDisclaimer: 'इस सत्र के लिए अस्वीकरण हटाएँ',
    disclaimerHeading: 'अस्वीकरण',
    messagesEmpty: 'अभी कोई संदेश नहीं है।',
    userMessageLabel: 'आपने पूछा',
    appMessageLabel: 'बेटर कॉल कानून',
    listening: 'सुन रहे हैं…',
    speakAgain: 'सुनकर दिखाएँ',
    stopSpeaking: 'सुनना बंद करें',
    statusBarUnavailable: 'सेवा उपलब्ध नहीं है',
    statusBarUnavailableBody:
      'बैकएंड से जवाब नहीं मिल रहा, इसलिए यह पृष्ठ केवल सीमित जानकारी दिखा रहा है।',
  },
}

/** The locale to use for speech synthesis when none is supplied. */
export function defaultLocaleFor(lang: LanguageCode): string {
  return lang === 'hi' ? 'hi-IN' : 'en-IN'
}
