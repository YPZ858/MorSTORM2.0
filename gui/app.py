"""Bilingual desktop workspace for independent and chained MorSTORM modules."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import monotonic
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import parameters
import runner


ZH = {
    'MorSTORM Workspace':'MorSTORM 工作台', 'SMLM processing':'单分子定位数据处理',
    'Variant':'版本', 'A frontend':'A 版入口', 'A drift uses the author MATLAB code.':'A 版漂移校正使用原作者 MATLAB 代码。',
    'B runs without MATLAB.':'B 版独立运行，无需 MATLAB。',
    'Workflow and input':'流程与输入', 'Modules run in the order shown.':'按下列顺序运行所选模块。',
    '1  Localization':'1  定位', '2  Drift correction':'2  漂移校正', '3  Morphology':'3  形态分析',
    'Localizer':'定位器', 'Drift method':'漂移方法',
    'Parameter preset':'参数预设', 'Time bins':'时间箱数', 'Frames per segment':'每段帧数',
    'Render pixel (nm)':'渲染像素（nm）', 'Camera pixel (nm)':'相机像素（nm）',
    'Scope':'处理范围', 'Single file':'单文件', 'Folder':'文件夹', 'Input':'输入',
    'Output parent':'结果父目录', 'Browse':'浏览', 'Restore audit values':'恢复审计参数',
    'Run selected modules':'运行所选模块', 'Run and results':'运行与结果', 'Ready':'就绪',
    'Preparing inputs':'准备输入', 'Checking file':'检查文件', 'Localization':'正在定位',
    'Drift correction':'正在校正漂移', 'Morphology':'MorphoLibJ 形态分析', 'Complete':'完成',
    'Completed with failures':'处理完成，含失败文件', 'Failed':'未完成', 'Check settings':'检查设置',
    'Execution log':'运行日志', 'Open job folder':'打开任务目录', 'Open file result':'打开当前文件结果',
    'A new result folder is created per run.':'每次运行创建独立结果目录。',
    'Selected: {name}':'已选：{name}',
    'Choose modules and a file or folder.':'选择模块及输入文件或文件夹。',
    'Choose a TIFF stack or a folder of TIFF stacks.':'选择 TIFF 堆栈或 TIFF 文件夹。',
    'Choose a CSV/HDF5 localization table or a folder of tables.':'选择 CSV/HDF5 定位表或定位表文件夹。',
    'Choose an existing coordinate table or a folder of tables.':'选择已有坐标表或坐标表文件夹。',
    'Morphology will use the input coordinates as supplied.':'形态分析将直接使用输入坐标。',
    'Morphology will use the uncorrected localization output.':'形态分析将使用未经漂移校正的定位结果。',
    'Confirm camera calibration and segmentation for new data.':'换数据时请核对相机标定和分段。',
    'Search radii {a:g} / {b:g} px · resampling {fold}':'搜索半径 {a:g} / {b:g} px · 重采样 {fold}',
    'Use the full stack for the initial frame check.':'预检使用 TIFF 堆栈帧数，定位后仍会检查有效帧。',
    'Input frame range ends at {frames:,}.':'输入帧范围截至 {frames:,}。',
    'File {index}/{total} · {name}':'文件 {index}/{total} · {name}',
    '{done}/{total} files processed · {time} elapsed':'已处理 {done}/{total} 个文件 · 用时 {time}',
    '{ok} completed · {bad} failed':'{ok} 个完成 · {bad} 个失败',
    '{n:,} localizations':'{n:,} 个定位点', 'Apply':'应用',
    'Task in progress':'任务运行中', 'Close the window after the current job finishes.':'请在当前任务结束后关闭窗口。',
    'Select input file':'选择输入文件', 'Select input folder':'选择输入文件夹', 'Select output parent':'选择结果父目录',
    'Advanced…':'高级参数…', 'Import preset…':'导入预设…', 'Save preset as…':'另存预设…',
    'Parameter':'参数', 'Unit':'单位', 'Value':'当前值', 'Audit default':'实测预设值',
    'Not specified':'未指定', 'Cancel':'取消', 'MorphoLibJ parameters':'MorphoLibJ 参数',
    '{method} parameters':'{method} 参数', 'Preset imported: {name}':'已导入预设：{name}',
    'Preset saved: {name}':'已保存预设：{name}', 'Audit parameters restored.':'已恢复实测参数。',
    'Preset import failed':'导入预设失败', 'Preset save failed':'保存预设失败',
    'Algorithm parameters are shared by A and B.':'A、B 版共用算法参数。',
    'MeanShift · error weighting {weight} · outlier threshold {threshold:g} nm':'MeanShift · 误差加权 {weight} · 离群阈值 {threshold:g} nm',
    'on':'开启', 'off':'关闭',
}
STAGE_TEXT = {'localize':'Localization','drift':'Drift correction','morphology':'Morphology'}
WORKFLOW_LABELS = dict(zip(runner.MODULES,('1  Localization','2  Drift correction','3  Morphology')))
BG, WHITE, INK, MUTED, BLUE, ICE, EDGE = '#edf2f6','#ffffff','#17324a','#5d7283','#126b8d','#e8f4fa','#d2dfe9'


class Workspace:
    def __init__(self, root, language):
        self.root = root
        self.lang = language
        root.title(self.t('MorSTORM Workspace'))
        root.geometry('1180x790')
        root.minsize(1000,710)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.version,self.a_entry = tk.StringVar(value='B'),tk.StringVar(value='Python')
        self.backend,self.preset = tk.StringVar(value='ThunderSTORM'),tk.StringVar(value='ThunderSTORM')
        self.method = tk.StringVar(value='MeanShift')
        self.modules = {stage:tk.BooleanVar(value=True) for stage in runner.MODULES}
        self.scope = tk.StringVar(value=self.t('Single file'))
        self.source = tk.StringVar()
        self.output = tk.StringVar(value=str(runner.WORK/'runs-v2'))
        self.pixel,self.period,self.render_pixel = tk.StringVar(value='103.5'),tk.StringVar(value='100'),tk.StringVar(value='10')
        self.period_label = tk.StringVar()
        self.hint,self.preview,self.version_note = tk.StringVar(),tk.StringVar(),tk.StringVar()
        self.phase,self.detail = tk.StringVar(value=self.t('Ready')),tk.StringVar(value=self.t('Choose modules and a file or folder.'))
        self.result_path = tk.StringVar(value=self.t('A new result folder is created per run.'))
        self.count_text = tk.StringVar()
        self.queue = Queue()
        self.running = False
        self.controls = []
        self.parameter_edits = {}
        self.profile = None
        self.job = self.current = None
        self.offsets = {}
        self.done = self.total = 0
        self.started = 0
        self.style()
        self.build()
        self.sync(reset=True)
        self.source.trace_add('write',self.update_hint)
        self.poll_token=root.after(250,self.poll)

    def t(self, text, **values):
        return (ZH.get(text,text) if self.lang=='zh' else text).format(**values)

    def style(self):
        s=ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.',font=('Microsoft YaHei UI',10),background=WHITE,foreground=INK)
        s.configure('Panel.TFrame',background=WHITE)
        s.configure('Heading.TLabel',font=('Microsoft YaHei UI',14,'bold'),background=WHITE,foreground=INK)
        s.configure('Hint.TLabel',font=('Microsoft YaHei UI',9),background=WHITE,foreground=MUTED)
        s.configure('Preview.TLabel',font=('Microsoft YaHei UI',9),background=ICE,foreground=INK,padding=(9,6))
        s.configure('Status.TLabel',font=('Microsoft YaHei UI',12,'bold'),background=ICE,foreground=BLUE,padding=(10,8))
        s.configure('TCombobox',padding=3,fieldbackground=WHITE,bordercolor=EDGE)
        s.map('TCombobox',fieldbackground=[('readonly',WHITE),('disabled',BG)])
        s.configure('TEntry',padding=3,fieldbackground=WHITE,bordercolor=EDGE)
        s.configure('TButton',padding=(8,4),background='#f6fafc',bordercolor=EDGE)
        s.configure('Start.TButton',padding=(9,7),background=BLUE,foreground='white',bordercolor=BLUE,
                    font=('Microsoft YaHei UI',10,'bold'))
        s.map('Start.TButton',background=[('disabled','#a3b8c3'),('active','#095b79')],foreground=[('disabled','white')])
        s.configure('Horizontal.TProgressbar',background=BLUE,troughcolor=ICE,bordercolor=EDGE)

    def label(self,parent,text,**kw):
        return ttk.Label(parent,text=self.t(text),**kw)

    def combo(self,parent,var,values,callback=None,width=15):
        c=ttk.Combobox(parent,textvariable=var,values=values,state='readonly',width=width)
        if callback:
            c.bind('<<ComboboxSelected>>',lambda _event:callback())
        self.controls.append(c)
        return c

    def entry(self,parent,var,width=13):
        e=ttk.Entry(parent,textvariable=var,width=width)
        self.controls.append(e)
        return e

    def button(self,parent,text,fn,**kw):
        b=ttk.Button(parent,text=self.t(text),command=fn,**kw)
        self.controls.append(b)
        return b

    def build(self):
        top=tk.Frame(self.root,bg=INK,padx=18,pady=10)
        top.pack(fill='x')
        tk.Label(top,text=self.t('MorSTORM Workspace'),bg=INK,fg='white',font=('Microsoft YaHei UI',20,'bold')).pack(side='left')
        engine=ttk.Frame(top,padding=(9,5))
        engine.pack(side='right')
        self.label(engine,'Variant').grid(row=0,column=0,padx=(0,7))
        for i,version in enumerate(('A','B'),1):
            b=ttk.Radiobutton(engine,text=version,value=version,variable=self.version,command=self.sync)
            b.grid(row=0,column=i,padx=(0,6)); self.controls.append(b)
        self.label(engine,'A frontend').grid(row=0,column=3,padx=(8,5))
        self.engine_combo=self.combo(engine,self.a_entry,('Python','MATLAB'),width=8)
        self.engine_combo.grid(row=0,column=4)
        ttk.Label(engine,textvariable=self.version_note,style='Hint.TLabel').grid(row=1,column=0,columnspan=5,sticky='w',pady=(2,0))

        body=tk.Frame(self.root,bg=BG,padx=12,pady=11)
        body.pack(fill='both',expand=True)
        body.columnconfigure(0,weight=6,uniform='panel'); body.columnconfigure(1,weight=5,uniform='panel')
        body.rowconfigure(0,weight=1)
        left,right=(ttk.Frame(body,style='Panel.TFrame',padding=13) for _ in range(2))
        left.grid(row=0,column=0,sticky='nsew',padx=(0,6)); right.grid(row=0,column=1,sticky='nsew',padx=(6,0))
        left.columnconfigure(1,weight=1); right.columnconfigure(0,weight=1); right.rowconfigure(6,weight=1)

        self.label(left,'Workflow and input',style='Heading.TLabel').grid(row=0,column=0,columnspan=3,sticky='w')
        self.label(left,'Modules run in the order shown.',style='Hint.TLabel').grid(row=1,column=0,columnspan=3,sticky='w',pady=(3,5))
        for row,stage in enumerate(runner.MODULES,2):
            b=ttk.Checkbutton(left,text=self.t(WORKFLOW_LABELS[stage]),variable=self.modules[stage],command=self.sync)
            b.grid(row=row,column=0,sticky='w',pady=4); self.controls.append(b)
        loc=ttk.Frame(left); loc.grid(row=2,column=1,columnspan=2,sticky='ew',padx=(7,0))
        self.loc_combo=self.combo(loc,self.backend,runner.BACKENDS,self.sync,width=17)
        self.loc_combo.pack(side='left',padx=(0,6))
        self.camera_button=self.button(loc,'Advanced…',lambda:self.edit_parameters(self.profile.backend))
        self.camera_button.pack(side='left')
        drift=ttk.Frame(left); drift.grid(row=3,column=1,columnspan=2,sticky='ew',padx=(7,0))
        self.method_combo=self.combo(drift,self.method,tuple(runner.METHODS),self.sync,width=13)
        self.label(drift,'Drift method',style='Hint.TLabel').grid(row=0,column=0,sticky='w')
        self.method_combo.grid(row=1,column=0,sticky='w',padx=(0,6))
        self.preset_combo=self.combo(drift,self.preset,runner.BACKENDS,self.sync,width=17)
        self.label(drift,'Parameter preset',style='Hint.TLabel').grid(row=0,column=1,sticky='w')
        self.preset_combo.grid(row=1,column=1,sticky='w')
        self.drift_button=self.button(drift,'Advanced…',lambda:self.edit_parameters(self.profile.method))
        self.drift_button.grid(row=1,column=2,sticky='w',padx=(6,0))
        morph=ttk.Frame(left); morph.grid(row=4,column=1,columnspan=2,sticky='w',padx=(7,0))
        self.label(morph,'Render pixel (nm)').pack(side='left',padx=(0,6))
        self.render_entry=self.entry(morph,self.render_pixel,6); self.render_entry.pack(side='left')
        self.morph_button=self.button(morph,'Advanced…',lambda:self.edit_parameters('morphology'))
        self.morph_button.pack(side='left',padx=(6,0))
        ttk.Separator(left).grid(row=5,column=0,columnspan=3,sticky='ew',pady=8)
        self.label(left,'Scope').grid(row=6,column=0,sticky='w',pady=3)
        self.combo(left,self.scope,(self.t('Single file'),self.t('Folder')),self.sync).grid(row=6,column=1,columnspan=2,sticky='ew',pady=3)
        self.input_entry=self.path_row(left,7,'Input',self.source,self.choose_input)
        self.out_entry=self.path_row(left,8,'Output parent',self.output,self.choose_output)
        settings=ttk.Frame(left); settings.grid(row=9,column=0,columnspan=3,sticky='ew',pady=(6,4))
        self.label(settings,'Camera pixel (nm)').pack(side='left',padx=(0,5))
        self.entry(settings,self.pixel,7).pack(side='left',padx=(0,11))
        ttk.Label(settings,textvariable=self.period_label).pack(side='left',padx=(0,5))
        self.period_entry=self.entry(settings,self.period,7); self.period_entry.pack(side='left')
        presets=ttk.Frame(left); presets.grid(row=10,column=0,columnspan=3,sticky='ew',pady=(2,6))
        self.button(presets,'Import preset…',self.import_preset).pack(side='left',padx=(0,5))
        self.save_button=self.button(presets,'Save preset as…',self.save_preset)
        self.save_button.pack(side='left',padx=(0,5))
        self.button(presets,'Restore audit values',self.restore_audit).pack(side='left')
        hint=ttk.Label(left,textvariable=self.hint,style='Hint.TLabel',wraplength=470,justify='left')
        hint.grid(row=11,column=0,columnspan=3,sticky='ew',pady=(2,6))
        preview=ttk.Label(left,textvariable=self.preview,style='Preview.TLabel',wraplength=470,justify='left')
        preview.grid(row=12,column=0,columnspan=3,sticky='ew',pady=(0,7))
        left.bind('<Configure>',lambda e:self.resize_labels(e.width,(hint,preview)))
        self.start_button=self.button(left,'Run selected modules',self.start,style='Start.TButton')
        self.start_button.grid(row=13,column=0,columnspan=3,sticky='ew')

        self.label(right,'Run and results',style='Heading.TLabel').grid(row=0,column=0,sticky='w',pady=(0,8))
        ttk.Label(right,textvariable=self.phase,style='Status.TLabel').grid(row=1,column=0,sticky='ew')
        detail=ttk.Label(right,textvariable=self.detail,style='Hint.TLabel',wraplength=440,justify='left')
        detail.grid(row=2,column=0,sticky='ew',pady=(6,4))
        self.progress=ttk.Progressbar(right,mode='determinate',maximum=1,value=0)
        self.progress.grid(row=3,column=0,sticky='ew')
        ttk.Label(right,textvariable=self.count_text,style='Hint.TLabel').grid(row=4,column=0,sticky='w',pady=(4,6))
        self.label(right,'Execution log').grid(row=5,column=0,sticky='w',pady=(1,4))
        frame=ttk.Frame(right); frame.grid(row=6,column=0,sticky='nsew'); frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1)
        self.log=tk.Text(frame,width=32,height=12,bg='#f7fafc',fg=INK,font=('Consolas',9),bd=0,padx=7,pady=7,wrap='word',state='disabled')
        self.log.grid(row=0,column=0,sticky='nsew')
        scroll=ttk.Scrollbar(frame,command=self.log.yview); scroll.grid(row=0,column=1,sticky='ns'); self.log.configure(yscrollcommand=scroll.set)
        result=ttk.Label(right,textvariable=self.result_path,style='Hint.TLabel',wraplength=440,justify='left')
        result.grid(row=7,column=0,sticky='ew',pady=(6,6))
        right.bind('<Configure>',lambda e:self.resize_labels(e.width,(detail,result)))
        actions=ttk.Frame(right); actions.grid(row=8,column=0,sticky='ew')
        self.open_job=ttk.Button(actions,text=self.t('Open job folder'),command=lambda:self.open_path(self.job.output),state='disabled')
        self.open_job.pack(side='left',padx=(0,6))
        self.open_file=ttk.Button(actions,text=self.t('Open file result'),command=lambda:self.open_path(self.current),state='disabled')
        self.open_file.pack(side='left')

    @staticmethod
    def resize_labels(width,labels):
        for label in labels:
            label.configure(wraplength=max(300,width-44))

    def path_row(self,parent,row,label,var,callback):
        self.label(parent,label).grid(row=row,column=0,sticky='w',pady=3,padx=(0,7))
        entry=self.entry(parent,var,20); entry.grid(row=row,column=1,sticky='ew',pady=3)
        self.button(parent,'Browse',callback).grid(row=row,column=2,padx=(5,0),pady=3)
        return entry

    def selected(self):
        return tuple(stage for stage in runner.MODULES if self.modules[stage].get())

    def folder_mode(self):
        return self.scope.get()==self.t('Folder')

    def sync(self,reset=False):
        chosen=self.selected()
        raw='localize' in chosen
        drift='drift' in chosen
        morph='morphology' in chosen
        before=self.profile
        backend=self.backend.get() if raw else self.preset.get()
        if raw:
            self.preset.set(backend)
        try:
            self.profile=runner.load_profile('raw' if raw else 'cached',backend,runner.METHODS[self.method.get()])
            self.audit_profile=runner.Profile(self.profile.mode,self.profile.backend,self.profile.method,
                                              deepcopy(self.profile.config))
            panels=(backend,self.profile.method,'morphology') if raw else (self.profile.method,'morphology')
            for panel in panels:
                edits=self.parameter_edits.get(parameters.section_key(panel,backend))
                if edits:
                    parameters.set_values(self.profile.config,panel,edits)
        except (OSError,ValueError) as error:
            self.profile=None
            self.detail.set(str(error))
        changed_kind=before is None or self.profile is None or before.mode!=self.profile.mode
        if changed_kind or self.folder_mode()!=getattr(self,'was_folder',False):
            path=str(self.profile.source) if raw and not self.folder_mode() and self.profile and self.profile.source else ''
            self.source.set(path)
            self.root.after_idle(self.input_entry.xview_moveto,1)
        self.was_folder=self.folder_mode()
        if self.profile and (reset or changed_kind or before.backend!=self.profile.backend or before.method!=self.profile.method):
            self.period.set(str(self.profile.period))
        if reset and self.profile:
            self.pixel.set(str(self.profile.config['input']['pixel_size_nm']))
            self.render_pixel.set(str(self.profile.config['render']['pixel_size_nm']))
        self.period_label.set(self.t('Time bins' if self.method.get()=='MeanShift' else 'Frames per segment'))
        self.version_note.set(self.t('A drift uses the author MATLAB code.' if self.version.get()=='A' else 'B runs without MATLAB.'))
        ready=self.profile is not None
        for widget,on in ((self.engine_combo,self.version.get()=='A'),(self.loc_combo,raw),(self.camera_button,raw and ready),
                          (self.method_combo,drift),(self.preset_combo,drift and not raw),(self.period_entry,drift),
                          (self.drift_button,drift and ready),(self.morph_button,morph and ready),
                          (self.render_entry,morph),(self.start_button,bool(chosen) and ready),(self.save_button,bool(chosen) and ready)):
            widget.state(['!disabled'] if on else ['disabled'])
        self.update_hint()
        lines=[self.t('Algorithm parameters are shared by A and B.'),self.t('Confirm camera calibration and segmentation for new data.')]
        if self.profile and drift:
            if self.profile.method=='meanshift':
                p=parameters.values(self.profile.config,'meanshift')
                lines.append(self.t('MeanShift · error weighting {weight} · outlier threshold {threshold:g} nm',
                                    weight=self.t('on' if p['calc_error'] else 'off'),threshold=p['outlier_error']))
            elif self.profile.method in ('npcloud','rrnpcloud'):
                p=self.profile.config['drift']['parameters']['npcloud']
                lines.append(self.t('Search radii {a:g} / {b:g} px · resampling {fold}',a=p['MaxSearchRadius_Pix1'],b=p['MaxSearchRadius_Pix2'],fold=p['ReSampleFold']))
        if morph and not drift:
            lines.append(self.t('Morphology will use the uncorrected localization output.' if raw else 'Morphology will use the input coordinates as supplied.'))
        self.preview.set('\n'.join(lines))

    def update_hint(self,*_args):
        hint=self.t('Choose a TIFF stack or a folder of TIFF stacks.' if self.modules['localize'].get() else
                    'Choose a CSV/HDF5 localization table or a folder of tables.' if self.modules['drift'].get() else
                    'Choose an existing coordinate table or a folder of tables.')
        source=self.source.get().strip()
        if source:
            hint+='\n'+self.t('Selected: {name}',name=Path(source).name or source)
        self.hint.set(hint)

    def choose_input(self):
        if self.folder_mode():
            path=filedialog.askdirectory(parent=self.root,title=self.t('Select input folder'))
        else:
            kinds=[('TIFF','*.tif *.tiff')] if self.modules['localize'].get() else [('CSV / HDF5','*.csv *.hdf5 *.h5')]
            path=filedialog.askopenfilename(parent=self.root,title=self.t('Select input file'),filetypes=kinds)
        if path:
            self.source.set(path)
            self.root.after_idle(self.input_entry.xview_moveto,1)

    def choose_output(self):
        path=filedialog.askdirectory(parent=self.root,title=self.t('Select output parent'))
        if path:
            self.output.set(path)
            self.root.after_idle(self.out_entry.xview_moveto,1)

    def edit_parameters(self, name):
        profile=self.profile
        language=1 if self.lang=='zh' else 0
        title=next((label for label,method in runner.METHODS.items() if method==name),name)
        dialog=tk.Toplevel(self.root)
        dialog.title(self.t('MorphoLibJ parameters') if name=='morphology' else self.t('{method} parameters',method=title))
        dialog.geometry('820x620' if name=='ThunderSTORM' else '750x440')
        dialog.minsize(600,340)
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog,text=parameters.FIXED[name][language],wraplength=570,justify='left',padding=10).pack(fill='x')
        frame=ttk.Frame(dialog,padding=(10,0))
        frame.pack(fill='both',expand=True)
        canvas=tk.Canvas(frame,bg=WHITE,highlightthickness=0)
        scroll=ttk.Scrollbar(frame,command=canvas.yview)
        scroll.pack(side='right',fill='y')
        canvas.pack(side='left',fill='both',expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        panel=ttk.Frame(canvas)
        panel.columnconfigure(2,weight=1)
        window=canvas.create_window(0,0,window=panel,anchor='nw')
        panel.bind('<Configure>',lambda _event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))
        dialog.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-int(event.delta/120),'units'))
        current=parameters.values(profile.config,name)
        defaults=parameters.values(self.audit_profile.config,name)
        shared={'camera_pixel':self.pixel,'render_pixel':self.render_pixel,
                'segment_frames':self.period,'nTimeBin':self.period}
        for index,label in enumerate(('Parameter','Unit','Value','Audit default')):
            self.label(panel,label).grid(row=0,column=index,sticky='w',padx=5,pady=(0,4))
        fields={}
        for row,field in enumerate(parameters.FIELDS[name],1):
            unit=field.unit.split(' / ')[-1 if language else 0]
            self.label(panel,field.zh if language else field.en).grid(row=row,column=0,sticky='w',padx=5,pady=3)
            self.label(panel,unit,style='Hint.TLabel').grid(row=row,column=1,sticky='w',padx=5,pady=3)
            value=shared[field.key].get() if field.key in shared else parameters.display(current.get(field.key))
            variable=tk.StringVar(value=value)
            fields[field.key]=variable
            if field.choices:
                choices=(('',)+field.choices) if field.optional else field.choices
                control=ttk.Combobox(panel,textvariable=variable,values=choices,state='readonly',width=13)
            else:
                control=ttk.Entry(panel,textvariable=variable,width=19)
            control.grid(row=row,column=2,sticky='ew',padx=5,pady=3)
            default=parameters.display(defaults.get(field.key)) or self.t('Not specified')
            ttk.Label(panel,text=default,wraplength=144,style='Hint.TLabel').grid(row=row,column=3,sticky='w',padx=5,pady=3)

        def apply():
            edits={key:variable.get() for key,variable in fields.items()}
            try:
                candidate=deepcopy(profile.config)
                parameters.set_values(candidate,name,edits)
            except ValueError as error:
                messagebox.showerror(self.t('Check settings'),str(error),parent=dialog)
                return
            self.parameter_edits[parameters.section_key(name,profile.backend)]=edits
            for key,var in shared.items():
                if key in edits:
                    var.set(edits[key])
            dialog.destroy()
            self.sync()

        actions=ttk.Frame(dialog,padding=10)
        actions.pack(fill='x')
        ttk.Button(actions,text=self.t('Apply'),command=apply).pack(side='right')
        ttk.Button(actions,text=self.t('Cancel'),command=dialog.destroy).pack(side='right',padx=(0,6))
        dialog.bind('<Return>',lambda _e:apply())
        dialog.bind('<Escape>',lambda _e:dialog.destroy())

    def restore_audit(self):
        self.parameter_edits.clear()
        self.sync(reset=True)
        self.detail.set(self.t('Audit parameters restored.'))

    def import_preset(self):
        path=filedialog.askopenfilename(parent=self.root,title=self.t('Import preset…'),filetypes=[('JSON','*.json')])
        if not path:
            return
        try:
            profile,modules=parameters.import_preset(Path(path),self.preset.get())
        except (OSError,ValueError) as error:
            messagebox.showerror(self.t('Preset import failed'),str(error),parent=self.root)
            return
        panels=(profile.backend,profile.method,'morphology') if profile.mode=='raw' else (profile.method,'morphology')
        for name in panels:
            self.parameter_edits[parameters.section_key(name,profile.backend)]=parameters.values(profile.config,name)
        for module,variable in self.modules.items():
            variable.set(module in modules)
        self.backend.set(profile.backend)
        self.preset.set(profile.backend)
        self.method.set(next(label for label,method in runner.METHODS.items() if method==profile.method))
        self.sync(reset=True)
        self.pixel.set(parameters.display(profile.config['input']['pixel_size_nm']))
        self.detail.set(self.t('Preset imported: {name}',name=Path(path).name))

    def save_preset(self):
        try:
            config=parameters.export_preset(self.profile,self.selected(),self.pixel.get(),self.period.get(),self.render_pixel.get())
        except ValueError as error:
            messagebox.showerror(self.t('Preset save failed'),str(error),parent=self.root)
            return
        path=filedialog.asksaveasfilename(parent=self.root,title=self.t('Save preset as…'),defaultextension='.json',
                                          initialfile=f'{self.profile.backend.lower()}-{self.profile.method}.json',filetypes=[('JSON','*.json')])
        if path:
            try:
                runner.save_json(Path(path),config)
            except OSError as error:
                messagebox.showerror(self.t('Preset save failed'),str(error),parent=self.root)
            else:
                self.detail.set(self.t('Preset saved: {name}',name=Path(path).name))

    def start(self):
        if self.running or self.profile is None:
            return
        try:
            engine='B Python' if self.version.get()=='B' else f'A {self.a_entry.get()}'
            self.job=runner.make_job(self.profile,engine,self.source.get(),self.folder_mode(),self.selected(),self.output.get(),
                                     self.pixel.get(),self.period.get(),None,self.render_pixel.get())
        except (OSError,ValueError) as error:
            self.phase.set(self.t('Check settings')); self.detail.set(str(error)); return
        self.running=True; self.current=None; self.done=self.total=0; self.started=monotonic()
        self.offsets.clear(); self.phase.set(self.t('Preparing inputs')); self.detail.set(engine)
        self.result_path.set(str(self.job.output)); self.progress.configure(maximum=1,value=0)
        self.open_job.state(['disabled']); self.open_file.state(['disabled'])
        for control in self.controls:
            control.state(['disabled'])
        self.log.configure(state='normal'); self.log.delete('1.0','end'); self.log.configure(state='disabled')
        Thread(target=runner.run,args=(self.job,lambda k,v:self.queue.put((k,v))),daemon=True).start()

    def append(self,text):
        self.log.configure(state='normal'); self.log.insert('end',text)
        line=int(self.log.index('end-1c').split('.')[0])
        if line>2500:
            self.log.delete('1.0',f'{line-2000}.0')
        self.log.see('end'); self.log.configure(state='disabled')

    def tail(self):
        if self.current is None:
            return
        files=[self.current/n for n in ('localization.log','localized.thunderstorm.log','morpholibj.log')]
        files.extend((self.current/'drift-author').glob('*/matlab.log'))
        for path in files:
            try:
                with path.open('rb') as file:
                    file.seek(self.offsets.get(path,0)); data=file.read(16384)
                    if data:
                        self.offsets[path]=file.tell(); self.append(f'[{path.name}] {data.decode("utf-8",errors="replace")}')
            except OSError:
                pass

    def handle(self,event,value):
        if event=='batch_start':
            self.total=value; self.progress.configure(maximum=value); self.open_job.state(['!disabled'])
        elif event=='file':
            index,total,name,self.current=value
            self.phase.set(self.t('Checking file')); self.detail.set(self.t('File {index}/{total} · {name}',index=index,total=total,name=name))
            self.append(f'\n[{index}/{total}] {name}\n'); self.open_file.state(['!disabled'])
        elif event=='inspection':
            self.append(self.t('Input frame range ends at {frames:,}.',frames=value)+'\n')
            if self.modules['localize'].get() and self.modules['drift'].get():
                self.append(self.t('Use the full stack for the initial frame check.')+'\n')
        elif event=='stage':
            self.phase.set(self.t(STAGE_TEXT[value]))
        elif event=='log':
            self.append(value)
        elif event=='file_done':
            self.tail(); self.done+=1; self.progress.configure(value=self.done)
            if value['status']=='failed':
                self.append(f'{self.t("Failed")} · {value["error"]}\n')
            else:
                self.append(self.t('{n:,} localizations',n=value['localizations'])+'\n')
        elif event in ('complete','error'):
            self.running=False
            for widget in self.controls:
                widget.state(['!disabled'])
            self.sync()
            if event=='error':
                self.phase.set(self.t('Failed')); self.detail.set(str(value)[:240]); self.append(str(value)+'\n')
            else:
                status = 'Complete' if not value['failed'] else 'Completed with failures' if value['completed'] else 'Failed'
                self.phase.set(self.t(status))
                self.detail.set(self.t('{ok} completed · {bad} failed',ok=value['completed'],bad=value['failed']))

    def poll(self):
        try:
            for _ in range(100):
                self.handle(*self.queue.get_nowait())
        except Empty:
            pass
        if self.running:
            seconds=int(monotonic()-self.started)
            self.count_text.set(self.t('{done}/{total} files processed · {time} elapsed',done=self.done,total=self.total,time=f'{seconds//60}:{seconds%60:02d}'))
            self.tail()
        self.poll_token=self.root.after(350,self.poll)

    def open_path(self,path):
        try:
            os.startfile(path)
        except OSError as error:
            messagebox.showerror(self.t('Failed'),str(error),parent=self.root)

    def close(self):
        if self.running:
            messagebox.showinfo(self.t('Task in progress'),self.t('Close the window after the current job finishes.'),parent=self.root)
        else:
            self.root.after_cancel(self.poll_token)
            self.root.destroy()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--lang',choices=('zh','en'),default='zh')
    args=parser.parse_args()
    root=tk.Tk()
    Workspace(root,args.lang)
    root.mainloop()


if __name__=='__main__':
    main()
