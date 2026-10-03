import vue from 'eslint-plugin-vue'
import parser from '@typescript-eslint/parser'
export default [
  { ignores: ['node_modules/**', 'dist/**'] },
  ...vue.configs['flat/essential'],
  { files: ['**/*.ts'], languageOptions: { parser } },
  { files: ['**/*.vue'], languageOptions: { parserOptions: { parser } } },
]
