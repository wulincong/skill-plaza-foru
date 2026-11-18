/* ============================================================
   内置演示附件（一键测试）
   ------------------------------------------------------------
   内容直接从仓库内置样例目录导入（单一数据源），
   进入声明了 demoFile 的工作台时自动上传并挂到附件区，
   可随时移除换成自己的文件。
   ============================================================ */

import networkResume from '../../../.agents/skills/career-guidance/examples/resumes/01-计算机网络技术-运维实习.md?raw'
import equipmentResume from '../../../.agents/skills/career-guidance/examples/resumes/02-机电一体化-设备技术员.md?raw'
import commerceResume from '../../../.agents/skills/career-guidance/examples/resumes/03-电子商务-运营实习.md?raw'
import manufacturingResume from '../../../.agents/skills/career-guidance/examples/resumes/04-生产制造类.md?raw'
import operationsResume from '../../../.agents/skills/career-guidance/examples/resumes/05-运营类.md?raw'
import salesResume from '../../../.agents/skills/career-guidance/examples/resumes/06-销售类.md?raw'
import resume from '../../../test-data/测试简历-Java后端实习.md?raw'
import schedInfo from '../../../.agents/skills/course-scheduling/examples/demo-school/01-信息.csv?raw'
import schedTasks from '../../../.agents/skills/course-scheduling/examples/demo-school/05-教学任务.csv?raw'
import schedClasses from '../../../.agents/skills/course-scheduling/examples/demo-school/02-班级.csv?raw'
import schedTeachers from '../../../.agents/skills/course-scheduling/examples/demo-school/03-教师.csv?raw'
import schedRooms from '../../../.agents/skills/course-scheduling/examples/demo-school/04-教室.csv?raw'
import schedTimetable from '../../../.agents/skills/course-scheduling/examples/demo-school/06-作息时间.csv?raw'
import schedCalendar from '../../../.agents/skills/course-scheduling/examples/demo-school/07-校历.csv?raw'
import schedBlocks from '../../../.agents/skills/course-scheduling/examples/demo-school/08-占用约束.csv?raw'

export interface DemoFile {
  filename: string
  content: string
}

export const DEMO_FILES: Record<string, DemoFile> = {
  networkResume: { filename: '01-计算机网络技术-运维实习.md', content: networkResume },
  equipmentResume: { filename: '02-机电一体化-设备技术员.md', content: equipmentResume },
  commerceResume: { filename: '03-电子商务-运营实习.md', content: commerceResume },
  manufacturingResume: { filename: '04-生产制造类.md', content: manufacturingResume },
  operationsResume: { filename: '05-运营类.md', content: operationsResume },
  salesResume: { filename: '06-销售类.md', content: salesResume },
  resume: { filename: '测试简历-Java后端实习.md', content: resume },
  schedInfo: { filename: '01-信息.csv', content: schedInfo },
  schedTasks: { filename: '05-教学任务.csv', content: schedTasks },
  schedClasses: { filename: '02-班级.csv', content: schedClasses },
  schedTeachers: { filename: '03-教师.csv', content: schedTeachers },
  schedRooms: { filename: '04-教室.csv', content: schedRooms },
  schedTimetable: { filename: '06-作息时间.csv', content: schedTimetable },
  schedCalendar: { filename: '07-校历.csv', content: schedCalendar },
  schedBlocks: { filename: '08-占用约束.csv', content: schedBlocks },
}
