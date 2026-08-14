import { useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquareText } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { getErrorMessage } from '../lib/api'
import { Button } from '../components/ui/Button'
import { Field, Input } from '../components/ui/Form'
import { Alert } from '../components/ui/Misc'

export function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    try {
      await login.mutateAsync({ email, password })
    } catch (err) {
      setError(getErrorMessage(err, 'Login failed'))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="mb-8 flex flex-col items-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
            <MessageSquareText className="h-5.5 w-5.5" />
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
            Welcome back
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Sign in to MessageFlow to manage your campaigns.
          </p>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-card dark:border-zinc-800 dark:bg-zinc-900"
        >
          {error && <Alert tone="error">{error}</Alert>}
          <Field label="Email" required>
            <Input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
            />
          </Field>
          <Field label="Password" required>
            <Input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
            />
          </Field>
          <Button type="submit" className="w-full" size="lg" loading={login.isPending}>
            Sign in
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
          No account yet?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}
