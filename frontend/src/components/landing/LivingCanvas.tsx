import React from 'react';
import { motion } from 'framer-motion';
import { Layer0Ambient } from './ui/Layer0Ambient';
import { LivePrompt } from './ui/LivePrompt';
import { LivePlanner } from './ui/LivePlanner';
import { LiveArchitecture } from './ui/LiveArchitecture';
import { MockEditor } from './ui/MockEditor';
import { RealisticTerminal } from './ui/RealisticTerminal';
import { LiveBrowser } from './ui/LiveBrowser';
import { AmbientFloat } from './ui/AmbientFloat';
import { GlowButton } from './ui/GlowButton';
import { Bot, ChevronRight, Code2, Zap, Database, GitBranch } from 'lucide-react';

export const LivingCanvas: React.FC = () => {
  return (
    <div className="relative w-full bg-[#FAF8F4] overflow-hidden selection:bg-[#F47A20] selection:text-white">
      {/* Layer 0: The Global Atmosphere */}
      <Layer0Ambient />

      <div className="relative z-10 w-full max-w-[1600px] mx-auto">
        
        {/* =========================================
            VIEWPORT 1: The Engineering Desktop (Hero)
            "What is Yantrika?" 
            ========================================= */}
        <section className="relative min-h-screen pt-32 pb-20 flex flex-col items-center justify-center px-6">
          {/* Asymmetric Typography */}
          <div className="w-full max-w-7xl relative z-20 mb-16 pointer-events-none">
            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 1 }}
              className="text-[12vw] md:text-[7vw] font-black leading-[0.85] tracking-tighter text-[#1F2937] mix-blend-multiply opacity-90"
            >
              The AI
              <br />
              <span className="ml-[10vw] md:ml-[5vw]">that ships</span>
              <br />
              <span className="ml-[20vw] md:ml-[15vw] text-[#F47A20]">software.</span>
            </motion.h1>
          </div>

          {/* The Desktop - Destroyed Grid, Overlapping */}
          <div className="w-full max-w-6xl relative h-[600px] md:h-[800px] pointer-events-none">
            {/* Prompt - Top Center */}
            <AmbientFloat delay={0} duration={12} className="absolute top-[10%] left-1/2 -translate-x-1/2 z-50 w-[90%] md:w-[600px] pointer-events-auto">
              <LivePrompt />
            </AmbientFloat>

            {/* Planner - Left, tucked slightly under Prompt, rotated */}
            <AmbientFloat delay={2} duration={14} className="absolute top-[35%] left-[5%] md:left-[10%] z-40 w-[280px] -rotate-2 pointer-events-auto">
              <LivePlanner />
            </AmbientFloat>

            {/* Architecture - Right, rotated opposite */}
            <AmbientFloat delay={1} duration={15} className="absolute top-[30%] right-[5%] md:right-[5%] z-30 w-[300px] md:w-[400px] rotate-1 pointer-events-auto">
              <LiveArchitecture />
            </AmbientFloat>

            {/* Code - Bottom Left, blurred slightly in background */}
            <AmbientFloat delay={3} duration={13} className="absolute top-[60%] left-[2%] md:left-0 z-20 w-[95%] md:w-[500px] -rotate-1 pointer-events-auto blur-[1px] opacity-90">
              <div className="scale-90 origin-bottom-left">
                <MockEditor />
              </div>
            </AmbientFloat>

            {/* Browser - Bottom Right, huge */}
            <AmbientFloat delay={0.5} duration={16} className="absolute top-[50%] right-[-5%] md:right-[10%] z-40 w-[110%] md:w-[600px] rotate-2 pointer-events-auto">
              <LiveBrowser />
            </AmbientFloat>
          </div>
        </section>


        {/* =========================================
            VIEWPORT 2: How it builds (Workflow)
            "How does it think?" -> Transitioning to Code
            ========================================= */}
        <section className="relative min-h-[120vh] py-32 flex flex-col items-center justify-center px-6">
          {/* Deep Gradient Mask to blend scenes */}
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#F4F1EA]/50 to-transparent pointer-events-none z-0" />

          <div className="w-full max-w-7xl relative z-10 flex flex-col md:flex-row items-center gap-12">
            
            <div className="flex-1 space-y-8">
              <h2 className="text-5xl md:text-7xl font-bold tracking-tight text-[#1F2937] leading-none">
                One Prompt. <br/>
                <span className="text-[#9CA3AF]">Infinite Engineers.</span>
              </h2>
              <p className="text-xl text-[#4B5563] max-w-md leading-relaxed">
                Watch Yantrika decompose your vision into specifications, architect the system, and allocate specialized agents in real-time.
              </p>
              <ul className="space-y-4">
                {[
                  { icon: <Bot size={20}/>, text: "Autonomous requirement analysis" },
                  { icon: <Code2 size={20}/>, text: "Multi-agent parallel coding" },
                  { icon: <Zap size={20}/>, text: "Instant artifact generation" }
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-[#1F2937] font-medium">
                    <div className="w-8 h-8 rounded-full bg-white border border-[#E9DED2] shadow-sm flex items-center justify-center text-[#F47A20]">
                      {item.icon}
                    </div>
                    {item.text}
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex-1 w-full relative h-[600px]">
              {/* Massive overlapping Terminal and Code */}
              <AmbientFloat delay={0} duration={14} className="absolute top-0 right-0 w-[120%] md:w-[700px] z-20">
                <RealisticTerminal />
              </AmbientFloat>
              <AmbientFloat delay={2} duration={12} className="absolute bottom-10 left-[-20%] md:left-[-100px] w-[100%] md:w-[600px] z-30 shadow-2xl">
                <MockEditor />
              </AmbientFloat>
            </div>

          </div>
        </section>


        {/* =========================================
            VIEWPORT 3: Infrastructure (The Factory Floor)
            "How does it scale?"
            ========================================= */}
        <section className="relative min-h-screen py-32 flex flex-col justify-center px-6 overflow-hidden">
          {/* Dark Overlay for industrial feel */}
          <div className="absolute inset-0 bg-[#0A0A0A]/95 backdrop-blur-[100px] z-0 rounded-[3rem] border border-white/10 mx-4 md:mx-12 overflow-hidden shadow-2xl">
            {/* Volumetric glow inside */}
            <div className="absolute top-0 right-0 w-[80vw] h-[80vw] bg-[#F47A20]/20 blur-[150px] rounded-full translate-x-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="w-full max-w-7xl mx-auto relative z-10 flex flex-col md:flex-row gap-12 items-center text-white py-20 px-8 md:px-16">
            <div className="flex-1 w-full relative h-[500px]">
              {/* Data stream connections SVG */}
              <svg className="absolute inset-0 w-full h-full opacity-30" viewBox="0 0 500 500">
                <motion.path 
                  d="M 100,100 C 250,100 250,400 400,400" 
                  stroke="#F47A20" strokeWidth="2" strokeDasharray="5 5" fill="none"
                  animate={{ strokeDashoffset: -20 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                />
                <motion.path 
                  d="M 100,400 C 250,400 250,100 400,100" 
                  stroke="#60A5FA" strokeWidth="2" strokeDasharray="5 5" fill="none"
                  animate={{ strokeDashoffset: 20 }} transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                />
              </svg>

              {/* Ecosystem Nodes */}
              <AmbientFloat delay={0} duration={10} className="absolute top-[20%] left-[20%] z-20">
                <div className="w-20 h-20 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center shadow-lg">
                  <Database size={32} className="text-white" />
                </div>
              </AmbientFloat>
              <AmbientFloat delay={1.5} duration={12} className="absolute bottom-[20%] left-[25%] z-20">
                <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center shadow-lg">
                  <GitBranch size={24} className="text-white" />
                </div>
              </AmbientFloat>
              <AmbientFloat delay={3} duration={14} className="absolute top-[40%] right-[10%] z-20">
                <div className="w-24 h-24 rounded-2xl bg-[#F47A20] flex items-center justify-center shadow-[0_0_50px_rgba(244,122,32,0.4)]">
                  <Zap size={40} className="text-white" />
                </div>
              </AmbientFloat>
            </div>

            <div className="flex-1 space-y-8">
              <h2 className="text-5xl md:text-7xl font-bold tracking-tight leading-none">
                Build. <br/>
                Watch. <br/>
                <span className="text-[#F47A20]">Deploy.</span>
              </h2>
              <p className="text-lg text-gray-400 max-w-md">
                Connected directly to your cloud infrastructure. Yantrika doesn't just write code—it manages dependencies, configures Docker, pushes to GitHub, and deploys to Vercel.
              </p>
            </div>
          </div>
        </section>


        {/* =========================================
            VIEWPORT 4: Launch (CTA)
            ========================================= */}
        <section className="relative min-h-[60vh] flex flex-col items-center justify-center px-6 text-center mt-32 mb-32">
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            whileInView={{ scale: 1, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1 }}
            className="space-y-8 relative z-10"
          >
            <h2 className="text-6xl md:text-8xl font-black text-[#1F2937] tracking-tighter">
              Start <span className="text-[#F47A20]">Building.</span>
            </h2>
            <p className="text-xl text-[#4B5563] max-w-xl mx-auto font-medium">
              Join the elite teams using autonomous agents to ship software faster than ever before.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-8">
              <GlowButton className="px-10 h-16 text-lg">
                <span className="flex items-center gap-2">
                  Launch Workspace <ChevronRight size={20} />
                </span>
              </GlowButton>
              <button className="px-8 h-16 rounded-full font-bold text-[#4B5563] hover:text-[#1F2937] transition-colors flex items-center gap-2 border-2 border-transparent hover:border-[#E9DED2] bg-white shadow-sm hover:shadow-md">
                View Documentation
              </button>
            </div>
          </motion.div>
        </section>

      </div>
    </div>
  );
};
