import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { motion, useReducedMotion } from "motion/react"
import {
  AlertCircle,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRound,
  Building2,
} from "lucide-react"
import { ParticleSphere } from "./ParticleSphere"
import { useAuth } from "../../context/AuthContext"
import "./auth.css"

type FormValues = {
  name: string
  email: string
  password: string
  confirmPassword: string
  institution: string
  terms: boolean
}

type FormErrors = Partial<Record<keyof FormValues, string>>

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(values: FormValues, registration: boolean): FormErrors {
  const errors: FormErrors = {}
  if (registration && !values.name.trim()) errors.name = "Enter your full name."
  if (!values.email.trim()) errors.email = "Enter your email address."
  else if (!emailPattern.test(values.email.trim())) errors.email = "Enter a valid email address like name@oxford.ac.uk."

  if (!values.password) {
    errors.password = "Enter your password."
  } else if (values.password.length < 8) {
    errors.password = "Password must be at least 8 characters."
  } else if (registration) {
    if (!/[A-Z]/.test(values.password)) {
      errors.password = "Include at least one uppercase letter."
    } else if (!/[a-z]/.test(values.password)) {
      errors.password = "Include at least one lowercase letter."
    } else if (!/\d/.test(values.password)) {
      errors.password = "Include at least one number."
    } else if (!/[!@#$%^&*(),.?":{}|<>_~`\-+=\[\]\\;'/]/.test(values.password)) {
      errors.password = "Include at least one special character."
    }
  }

  if (registration && values.password !== values.confirmPassword) {
    errors.confirmPassword = "Passwords must match."
  }
  if (registration && !values.terms) errors.terms = "Accept the terms to create your account."
  return errors
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return (
    <p className="field-error" id={id} aria-live="polite">
      {message && (
        <>
          <AlertCircle size={13} aria-hidden="true" />
          {message}
        </>
      )}
    </p>
  )
}

function InputField({
  id,
  label,
  icon,
  error,
  children,
}: {
  id: string
  label: string
  icon: ReactNode
  error?: string
  children: ReactNode
}) {
  const errorId = `${id}-error`
  return (
    <label className="field" htmlFor={id}>
      <span>{label}</span>
      <span className={error ? "input-wrap input-error" : "input-wrap"}>
        {icon}
        {children}
      </span>
      <FieldError id={errorId} message={error} />
    </label>
  )
}

function useFormState(initial: FormValues, registration: boolean) {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<FormErrors>({})
  const [touched, setTouched] = useState<Partial<Record<keyof FormValues, boolean>>>({})
  const refs = useRef<Partial<Record<keyof FormValues, HTMLInputElement | null>>>({})

  const register = (name: keyof FormValues) => (element: HTMLInputElement | null) => {
    refs.current[name] = element
  }

  const update = (name: keyof FormValues, value: string | boolean) => {
    const next = { ...values, [name]: value }
    setValues(next)
    if (touched[name] || errors[name]) {
      setErrors((current) => ({ ...current, [name]: validate(next, registration)[name] }))
    }
  }

  const blur = (name: keyof FormValues) => {
    setTouched((current) => ({ ...current, [name]: true }))
    setErrors((current) => ({ ...current, [name]: validate(values, registration)[name] }))
  }

  const validateAll = () => {
    const nextErrors = validate(values, registration)
    setErrors(nextErrors)
    setTouched({ name: true, email: true, password: true, confirmPassword: true, institution: true, terms: true })
    const first = (["name", "email", "password", "confirmPassword", "terms"] as const).find(
      (key) => nextErrors[key]
    )
    if (first) refs.current[first]?.focus()
    return nextErrors
  }

  return { values, errors, register, update, blur, validateAll }
}

function PasswordInput({
  id,
  value,
  error,
  autoComplete,
  onChange,
  onBlur,
  inputRef,
}: {
  id: string
  value: string
  error?: string
  autoComplete: string
  onChange: (value: string) => void
  onBlur: () => void
  inputRef: (element: HTMLInputElement | null) => void
}) {
  const [visible, setVisible] = useState(false)
  const errorId = `${id}-error`
  return (
    <InputField
      id={id}
      label={id === "password" ? "Password" : "Confirm password"}
      icon={<LockKeyhole size={17} />}
      error={error}
    >
      <input
        ref={inputRef}
        id={id}
        name={id}
        type={visible ? "text" : "password"}
        value={value}
        placeholder="••••••••"
        autoComplete={autoComplete}
        minLength={8}
        required
        aria-invalid={Boolean(error)}
        aria-describedby={errorId}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
      />
      <button
        className="password-toggle"
        type="button"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        onClick={() => setVisible((current) => !current)}
      >
        {visible ? <EyeOff size={17} /> : <Eye size={17} />}
      </button>
    </InputField>
  )
}

function LoginCard({ onSwitchToRegister }: { onSwitchToRegister: () => void }) {
  const { signIn } = useAuth()
  const [message, setMessage] = useState("")
  const [isError, setIsError] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [shake, setShake] = useState(0)
  const reducedMotion = useReducedMotion()

  const { values, errors, register, update, blur, validateAll } = useFormState(
    {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
      institution: "",
      terms: false,
    },
    false
  )

  useEffect(() => {
    if (window.innerWidth > 760) {
      document.querySelector<HTMLInputElement>('.auth-card input[name="email"]')?.focus()
    }
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors = validateAll()
    if (Object.keys(nextErrors).length) {
      if (!reducedMotion) setShake((current) => current + 1)
      return
    }

    setIsSubmitting(true)
    setMessage("")
    setIsError(false)

    try {
      await signIn(values.email, values.password)
      setIsSubmitting(false)
      setIsSuccess(true)
      setMessage("Welcome back to ORION.")
    } catch (err: unknown) {
      setIsSubmitting(false)
      setIsError(true)
      const errorMsg = err instanceof Error ? err.message : "Authentication failed. Please check your credentials."
      setMessage(errorMsg)
      if (!reducedMotion) setShake((current) => current + 1)
    }
  }

  return (
    <motion.div
      className="auth-card"
      initial={{ opacity: 0, y: 22 }}
      animate={shake ? { opacity: 1, y: 0, x: [0, -6, 6, -4, 4, 0] } : { opacity: 1, y: 0 }}
      transition={{ duration: shake ? 0.25 : 0.8, delay: shake ? 0 : 0.35, ease: "easeOut" }}
    >
      <div className="auth-tabs" role="tablist" aria-label="Account access type">
        <button className="auth-tab active" role="tab" aria-selected="true" type="button">
          Sign in
        </button>
        <button
          className="auth-tab"
          role="tab"
          aria-selected="false"
          type="button"
          onClick={onSwitchToRegister}
        >
          Create account
        </button>
      </div>
      <div className="auth-heading">
        <p className="card-kicker">WELCOME BACK</p>
        <h2>Enter your orbit</h2>
        <p>Sign in to continue your research session.</p>
      </div>
      <form onSubmit={submit} noValidate>
        <InputField id="email" label="Email address" icon={<Mail size={17} />} error={errors.email}>
          <input
            ref={register("email")}
            id="email"
            name="email"
            type="email"
            value={values.email}
            placeholder="researcher@institution.edu"
            autoComplete="username"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            required
            aria-invalid={Boolean(errors.email)}
            aria-describedby="email-error"
            onChange={(event) => update("email", event.target.value)}
            onBlur={() => blur("email")}
          />
        </InputField>
        <PasswordInput
          id="password"
          value={values.password}
          error={errors.password}
          autoComplete="current-password"
          inputRef={register("password")}
          onChange={(value) => update("password", value)}
          onBlur={() => blur("password")}
        />
        <div className="form-options">
          <label className="remember">
            <input type="checkbox" name="remember" />
            <span>Remember me</span>
          </label>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setMessage("Contact your administrator or institution lead for access credentials.")
              setIsError(false)
            }}
          >
            Forgot password?
          </button>
        </div>
        <button className="submit-button" type="submit" disabled={isSubmitting}>
          <span>{isSubmitting ? "Signing in..." : isSuccess ? "Welcome back" : "Sign in to ORION"}</span>
          {isSubmitting ? (
            <span className="spinner" aria-hidden="true" />
          ) : isSuccess ? (
            <Check size={18} />
          ) : (
            <ArrowRight size={18} />
          )}
        </button>
        {message && (
          <p className={`form-message ${isError ? "error-message" : ""}`} aria-live="polite">
            {message}
          </p>
        )}
      </form>
      <p className="auth-switch">
        New to ORION?{" "}
        <button type="button" onClick={onSwitchToRegister}>
          Create account
        </button>
      </p>
    </motion.div>
  )
}

function RegisterCard({ onSwitchToLogin }: { onSwitchToLogin: () => void }) {
  const { signUp } = useAuth()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [registrationError, setRegistrationError] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const reducedMotion = useReducedMotion()
  const [shake, setShake] = useState(0)

  const { values, errors, register, update, blur, validateAll } = useFormState(
    {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
      institution: "",
      terms: false,
    },
    true
  )

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextErrors = validateAll()
    if (Object.keys(nextErrors).length) {
      if (!reducedMotion) setShake((current) => current + 1)
      return
    }

    setIsSubmitting(true)
    setRegistrationError("")

    try {
      await signUp({
        name: values.name.trim(),
        email: values.email.trim(),
        password: values.password,
        institution: values.institution.trim() || undefined,
      })
      // Successful registration establishes session and auto-transitions
    } catch (err: unknown) {
      setIsSubmitting(false)
      const errorMsg =
        err instanceof Error ? err.message : "We couldn't create your account. Please try again."
      setRegistrationError(errorMsg)
      if (!reducedMotion) setShake((current) => current + 1)
    }
  }

  return (
    <motion.div
      className="auth-card"
      initial={{ opacity: 0, y: 22 }}
      animate={shake ? { opacity: 1, y: 0, x: [0, -6, 6, -4, 4, 0] } : { opacity: 1, y: 0 }}
      transition={{ duration: shake ? 0.25 : 0.8, delay: shake ? 0 : 0.35, ease: "easeOut" }}
    >
      <div className="auth-tabs" role="tablist" aria-label="Account access type">
        <button className="auth-tab" role="tab" aria-selected="false" type="button" onClick={onSwitchToLogin}>
          Sign in
        </button>
        <button className="auth-tab active" role="tab" aria-selected="true" type="button">
          Create account
        </button>
      </div>
      <div className="auth-heading">
        <p className="card-kicker">BEGIN YOUR RESEARCH</p>
        <h2>Create your account</h2>
        <p>Set up your secure ORION research profile.</p>
      </div>
      <form onSubmit={submit} noValidate>
        <InputField id="name" label="Full name" icon={<UserRound size={17} />} error={errors.name}>
          <input
            ref={register("name")}
            id="name"
            name="name"
            type="text"
            value={values.name}
            placeholder="Dr. Eleanor Vance"
            autoComplete="name"
            required
            aria-invalid={Boolean(errors.name)}
            aria-describedby="name-error"
            onChange={(event) => update("name", event.target.value)}
            onBlur={() => blur("name")}
          />
        </InputField>
        <InputField id="email" label="Email address" icon={<Mail size={17} />} error={errors.email}>
          <input
            ref={register("email")}
            id="email"
            name="email"
            type="email"
            value={values.email}
            placeholder="eleanor.vance@oxford.ac.uk"
            autoComplete="email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            required
            aria-invalid={Boolean(errors.email)}
            aria-describedby="email-error"
            onChange={(event) => update("email", event.target.value)}
            onBlur={() => blur("email")}
          />
        </InputField>
        <InputField
          id="institution"
          label="Institution / Affiliation (optional)"
          icon={<Building2 size={17} />}
          error={errors.institution}
        >
          <input
            ref={register("institution")}
            id="institution"
            name="institution"
            type="text"
            value={values.institution}
            placeholder="University of Oxford"
            autoComplete="organization"
            onChange={(event) => update("institution", event.target.value)}
            onBlur={() => blur("institution")}
          />
        </InputField>
        <InputField id="password" label="Password" icon={<LockKeyhole size={17} />} error={errors.password}>
          <input
            ref={register("password")}
            id="password"
            name="password"
            type={showPassword ? "text" : "password"}
            value={values.password}
            placeholder="••••••••"
            autoComplete="new-password"
            minLength={8}
            required
            aria-invalid={Boolean(errors.password)}
            aria-describedby="password-error"
            onChange={(event) => update("password", event.target.value)}
            onBlur={() => blur("password")}
          />
          <button
            className="password-toggle"
            type="button"
            aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword}
            onClick={() => setShowPassword((current) => !current)}
          >
            {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        </InputField>
        <PasswordInput
          id="confirmPassword"
          value={values.confirmPassword}
          error={errors.confirmPassword}
          autoComplete="new-password"
          inputRef={register("confirmPassword")}
          onChange={(value) => update("confirmPassword", value)}
          onBlur={() => blur("confirmPassword")}
        />
        <label className="remember terms">
          <input
            type="checkbox"
            name="terms"
            checked={values.terms}
            aria-invalid={Boolean(errors.terms)}
            aria-describedby="terms-error"
            onChange={(event) => update("terms", event.target.checked)}
            onBlur={() => blur("terms")}
          />
          <span>I agree to the ORION research terms and verified data usage policy.</span>
        </label>
        <FieldError id="terms-error" message={errors.terms} />
        <button className="submit-button" type="submit" disabled={isSubmitting}>
          <span>{isSubmitting ? "Creating account..." : "Create account"}</span>
          {isSubmitting ? <span className="spinner" aria-hidden="true" /> : <ArrowRight size={18} />}
        </button>
        {registrationError && (
          <p className="form-message error-message" aria-live="polite">
            {registrationError}
          </p>
        )}
      </form>
      <p className="auth-switch">
        Already have an account?{" "}
        <button type="button" onClick={onSwitchToLogin}>
          Sign in
        </button>
      </p>
    </motion.div>
  )
}

export function AuthHero({ onEnterDemo }: { onEnterDemo?: () => void } = {}) {
  const [mode, setMode] = useState<"login" | "register">(() => {
    if (typeof window !== "undefined") {
      const p = window.location.pathname
      const h = window.location.hash
      if (p === "/register" || h === "#register") return "register"
    }
    return "login"
  })

  return (
    <main className={mode === "register" ? "orion-auth-shell registration-page" : "orion-auth-shell"}>
      <motion.div
        className="sphere-layer"
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <ParticleSphere
          shellCount={9000}
          bandCount={2600}
          haloCount={1400}
          spinSpeed={0.22}
          scale={0.34}
        />
      </motion.div>
      <div className="orion-glow" aria-hidden="true" />
      <header className="orion-header">
        <a className="orion-brand" href="/" aria-label="ORION home">
          <span className="brand-mark">O</span>
          <span>ORION</span>
        </a>
        <div className="header-status flex items-center gap-3">
          {onEnterDemo && (
            <button
              type="button"
              onClick={onEnterDemo}
              className="px-3 py-1 rounded text-xs font-mono font-medium tracking-wide bg-[#2563EB]/20 text-[#60A5FA] border border-[#2563EB]/40 hover:bg-[#2563EB]/30 transition-colors flex items-center gap-1.5"
            >
              <span>Explore Public Demo</span>
              <ArrowRight size={13} />
            </button>
          )}
          <span className="status-dot" />
          <span>SECURE ACCESS</span>
        </div>
      </header>
      <section className="auth-layout" aria-label="ORION account access">
        <motion.div
          className="auth-intro"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
        >
          <p className="eyebrow">THE NEXT HORIZON</p>
          <h1>
            Navigate beyond
            <br />
            <em>the ordinary.</em>
          </h1>
          <p className="intro-copy">
            Your command center for verified research, evidence-grounded insights, and peer-reviewed rigor.
          </p>

          {/* Dual-Mode Gateway Option A: Public Demo */}
          {onEnterDemo && (
            <div className="mt-6 p-4 rounded-xl border border-[#ffb84c]/25 hover:border-[#ffb84c]/45 bg-[#17130f]/80 backdrop-blur-sm text-left shadow-xl shadow-black/40 hover:shadow-[0_8px_32px_rgba(255,184,76,0.08)] transition-all duration-200 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-semibold tracking-wider text-[#ffb84c] uppercase">
                  Option A • Public Evaluation
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                  No Login Required
                </span>
              </div>
              <div>
                <h3 className="text-base font-medium text-[#fff8eb] font-serif">Explore Public Demo</h3>
                <p className="text-xs text-[#fff8eb]/70 mt-1 leading-relaxed">
                  Evaluate evidence-grounded RAG on our curated 4-paper EPR literature corpus. Immediate access for visitors and recruiters.
                </p>
              </div>
              <button
                type="button"
                onClick={onEnterDemo}
                className="w-full py-2.5 px-3 rounded-lg text-xs font-mono font-semibold tracking-wide bg-gradient-to-r from-[#ffb84c] to-[#e59a27] hover:from-[#ffd083] hover:to-[#f0a634] text-[#17130f] flex items-center justify-center gap-2 transition-all shadow-md shadow-[#ffb84c]/20 hover:shadow-lg hover:shadow-[#ffb84c]/30 focus:outline-none focus:ring-2 focus:ring-[#ffb84c]/60 focus:ring-offset-2 focus:ring-offset-[#17130f]"
              >
                <span>Launch Public Demo Workspace</span>
                <ArrowRight size={14} className="text-[#17130f]" />
              </button>
            </div>
          )}

          <div className="intro-meta mt-4">
            <ShieldCheck size={18} />
            <span>Option B • Private Research Workspace (Sign in or create account)</span>
          </div>
        </motion.div>
        {mode === "register" ? (
          <RegisterCard onSwitchToLogin={() => setMode("login")} />
        ) : (
          <LoginCard onSwitchToRegister={() => setMode("register")} />
        )}
      </section>
      <footer className="orion-footer">
        <span>© 2026 ORION RESEARCH SYSTEMS</span>
        <span>ALL SYSTEMS NOMINAL</span>
      </footer>
    </main>
  )
}

