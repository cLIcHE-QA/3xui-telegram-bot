import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// D1b is a separate HTML entry; publishing/serving it needs a protected origin.
export default defineConfig({
 plugins:[react()],
 build:{rollupOptions:{input:{portal:"index.html",admin:"admin.html"}}},
 server:{host:"127.0.0.1"}
});
