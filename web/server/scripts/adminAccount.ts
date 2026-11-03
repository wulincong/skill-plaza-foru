/** Local operator command; no password in argv or deployment environment. */
import { randomBytes } from 'node:crypto'
import { AdminStore } from '../lib/adminStore.ts'

const [name = 'admin', option] = process.argv.slice(2)
const store = new AdminStore()
if (store.db.prepare('SELECT id FROM account').get() && option !== '--reset') {
  console.error('管理员已存在。需要重置时使用 node server/scripts/adminAccount.ts <账号名> --reset')
  process.exitCode = 1
} else {
  const password = randomBytes(20).toString('base64url')
  store.setAccount(name, password)
  console.log('账号：' + name + '\n初始密码：' + password + '\n请登录 /admin 并在账号设置中修改密码。')
}
store.db.close()
