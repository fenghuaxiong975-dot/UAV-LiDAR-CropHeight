using System;
using System.ComponentModel;
using System.Configuration;
using System.Data;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace WindowsFormsApp1
{
    public partial class Form2 : Form
    {
        private string _lasFilePath;
        private string _shpFilePath;
        private string _lastOutputCsv;

        public Form2()
        {
            InitializeComponent();
            this.StartPosition = FormStartPosition.CenterScreen;
            dataGridView1.Visible = false;
        }

        private void button1_Click(object sender, EventArgs e)
        {
            openFileDialog2.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            openFileDialog2.Filter = "点云文件 (*.las;*.laz)|*.las;*.laz|LAS 文件 (*.las)|*.las|LAZ 文件 (*.laz)|*.laz";
            if (openFileDialog2.ShowDialog() == DialogResult.OK)
            {
                _lasFilePath = openFileDialog2.FileName;
                textBox1.Text = _lasFilePath;
            }
        }

        private void button2_Click(object sender, EventArgs e)
        {
            openFileDialog1.InitialDirectory = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            openFileDialog1.Filter = "矢量文件 (*.shp)|*.shp";
            if (openFileDialog1.ShowDialog() == DialogResult.OK)
            {
                _shpFilePath = openFileDialog1.FileName;
                textBox2.Text = _shpFilePath;
            }
        }

        private void button4_Click(object sender, EventArgs e)
        {
            textBox3.Clear();
            string error = ValidateSelections();
            if (error != null)
            {
                textBox3.AppendText(error + Environment.NewLine);
                return;
            }

            textBox3.AppendText("输入文件检查通过。" + Environment.NewLine);
            textBox3.AppendText("当前开源版由“计算株高”一次完成小区分割、分类和 CHM 株高计算。" + Environment.NewLine);
        }

        private async void button5_Click(object sender, EventArgs e)
        {
            textBox4.Clear();
            string error = ValidateSelections();
            if (error != null)
            {
                textBox4.AppendText(error + Environment.NewLine);
                return;
            }

            string scriptPath = FindCropHeightScript();
            if (scriptPath == null)
            {
                textBox4.AppendText(
                    "未找到 python/crop_height.py。请从完整克隆的仓库中运行桌面程序。" + Environment.NewLine);
                return;
            }

            string inputDirectory = Path.GetDirectoryName(_lasFilePath);
            _lastOutputCsv = Path.Combine(inputDirectory, "plot_heights_CHM_batch.csv");
            string arguments = string.Join(" ", new[]
            {
                Quote(scriptPath),
                "--input", Quote(_lasFilePath),
                "--shp", Quote(_shpFilePath),
                "--output", Quote(_lastOutputCsv)
            });

            button5.Enabled = false;
            textBox4.AppendText("正在处理中..." + Environment.NewLine);

            try
            {
                ProcessResult result = await RunPythonScriptAsync(GetPythonExecutable(), arguments);
                textBox4.Clear();
                if (!string.IsNullOrWhiteSpace(result.StandardOutput))
                    textBox4.AppendText(result.StandardOutput.TrimEnd() + Environment.NewLine);
                if (!string.IsNullOrWhiteSpace(result.StandardError))
                    textBox4.AppendText(result.StandardError.TrimEnd() + Environment.NewLine);

                if (result.ExitCode != 0)
                {
                    textBox4.AppendText("Python 处理失败，退出码：" + result.ExitCode + Environment.NewLine);
                }
            }
            catch (Exception ex)
            {
                textBox4.AppendText("执行 Python 时出现错误: " + ex.Message + Environment.NewLine);
            }
            finally
            {
                button5.Enabled = true;
            }
        }

        private string ValidateSelections()
        {
            if (string.IsNullOrWhiteSpace(_lasFilePath) || !File.Exists(_lasFilePath))
                return "请选择有效的 LAS/LAZ 点云文件。";
            if (string.IsNullOrWhiteSpace(_shpFilePath) || !File.Exists(_shpFilePath))
                return "请选择有效的 SHP 小区矢量文件。";
            return null;
        }

        private static string GetPythonExecutable()
        {
            string configured = ConfigurationManager.AppSettings["PythonExe"];
            return string.IsNullOrWhiteSpace(configured) ? "python" : configured.Trim();
        }

        private static string FindCropHeightScript()
        {
            DirectoryInfo current = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
            for (int depth = 0; current != null && depth < 10; depth++, current = current.Parent)
            {
                string candidate = Path.Combine(current.FullName, "python", "crop_height.py");
                if (File.Exists(candidate))
                    return candidate;
            }
            return null;
        }

        private static string Quote(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private async Task<ProcessResult> RunPythonScriptAsync(string pythonPath, string arguments)
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = pythonPath,
                Arguments = arguments,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8
            };

            using (var process = new Process())
            {
                process.StartInfo = startInfo;
                process.Start();

                Task<string> stdoutTask = process.StandardOutput.ReadToEndAsync();
                Task<string> stderrTask = process.StandardError.ReadToEndAsync();
                await Task.WhenAll(stdoutTask, stderrTask);
                process.WaitForExit();

                return new ProcessResult
                {
                    ExitCode = process.ExitCode,
                    StandardOutput = stdoutTask.Result,
                    StandardError = stderrTask.Result
                };
            }
        }

        private sealed class ProcessResult
        {
            public int ExitCode { get; set; }
            public string StandardOutput { get; set; }
            public string StandardError { get; set; }
        }

        private void button11_Click(object sender, EventArgs e)
        {
            string csvFilePath = _lastOutputCsv;
            if (string.IsNullOrWhiteSpace(csvFilePath) || !File.Exists(csvFilePath))
                csvFilePath = ExtractCsvFilePath(textBox4.Text);

            if (string.IsNullOrWhiteSpace(csvFilePath) || !File.Exists(csvFilePath))
            {
                MessageBox.Show("CSV 文件路径无效或文件不存在！", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            DisplayCsvInDataGridView(csvFilePath);
            dataGridView1.Visible = true;
        }

        private static string ExtractCsvFilePath(string output)
        {
            string[] lines = output.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string line in lines)
            {
                string trimmed = line.Trim();
                if (!trimmed.StartsWith("Saved:", StringComparison.OrdinalIgnoreCase))
                    continue;

                string candidate = trimmed.Substring("Saved:".Length).Trim();
                int rowsSuffix = candidate.LastIndexOf(" (", StringComparison.Ordinal);
                if (rowsSuffix > 0)
                    candidate = candidate.Substring(0, rowsSuffix).Trim();
                if (candidate.EndsWith(".csv", StringComparison.OrdinalIgnoreCase))
                    return candidate;
            }
            return string.Empty;
        }

        private void DisplayCsvInDataGridView(string csvFilePath)
        {
            var dataTable = new DataTable();
            try
            {
                using (var reader = new StreamReader(csvFilePath))
                {
                    string header = reader.ReadLine();
                    if (header != null)
                    {
                        foreach (string column in header.Split(','))
                            dataTable.Columns.Add(column);
                    }

                    while (!reader.EndOfStream)
                    {
                        string row = reader.ReadLine();
                        if (row != null)
                            dataTable.Rows.Add(row.Split(','));
                    }
                }

                dataGridView1.DataSource = dataTable;
                dataGridView1.Refresh();
            }
            catch (Exception ex)
            {
                MessageBox.Show("读取 CSV 文件时出错: " + ex.Message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        // Designer-generated event hooks retained for compatibility.
        private void label1_Click(object sender, EventArgs e) { }
        private void label2_Click(object sender, EventArgs e) { }
        private void textBox1_TextChanged(object sender, EventArgs e) { }
        private void textBox2_TextChanged(object sender, EventArgs e) { }
        private void openFileDialog1_FileOk(object sender, CancelEventArgs e) { }
        private void textBox3_TextChanged(object sender, EventArgs e) { }
        private void progressBar1_Click(object sender, EventArgs e) { }
        private void Form2_Load(object sender, EventArgs e) { }
        private void label3_Click(object sender, EventArgs e) { }
        private void button3_Click(object sender, EventArgs e) { }
        private void dataGridView1_CellContentClick(object sender, DataGridViewCellEventArgs e) { }
    }
}
