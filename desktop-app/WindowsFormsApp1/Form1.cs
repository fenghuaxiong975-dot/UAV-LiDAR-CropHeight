using System;
using System.Drawing;
using System.Windows.Forms;

namespace WindowsFormsApp1
{
    public partial class Form1 : Form
    {
        private CheckBox showPasswordCheckbox;
        private const string UsernamePlaceholder = "请输入用户名";
        private const string PasswordPlaceholder = "请输入密码";

        public Form1()
        {
            InitializeComponent();
            InitializeForm();
            SetupControlStyles();
            SetupEventHandlers();
        }

        private void InitializeForm()
        {
            // 设置背景颜色
            this.BackColor = Color.LightGray;
            // 设置窗体标题
            this.Text = "登录界面";
            // 设置窗体大小
            this.Size = new Size(350, 300);
            // 居中显示窗体
            this.StartPosition = FormStartPosition.CenterScreen;
        }

        private void SetupControlStyles()
        {
            int centerX = (this.ClientSize.Width - 120) / 2;

            // 设置标题标签样式
            label3.Font = new Font("微软雅黑", 20, FontStyle.Bold);
            label3.ForeColor = Color.DarkBlue;
            label3.Text = "登录";
            label3.Location = new Point(120, 30);

            // 设置用户名标签样式
            label1.Font = new Font("微软雅黑", 12);
            label1.ForeColor = Color.Black;
            label1.Text = "用户名:";
            label1.Location = new Point(80, 80);

            // 设置用户名输入框样式
            user.Font = new Font("微软雅黑", 12);
            user.BackColor = Color.White;
            user.ForeColor = Color.Black;
            user.BorderStyle = BorderStyle.FixedSingle;
            user.Padding = new Padding(10);
            user.Location = new Point(80, 100);
            user.Size = new Size(200, 30);
            user.Text = UsernamePlaceholder;

            // 设置密码标签样式
            label2.Font = new Font("微软雅黑", 12);
            label2.ForeColor = Color.Black;
            label2.Text = "密码:";
            label2.Location = new Point(80, 130);

            // 设置密码输入框样式
            password.Font = new Font("微软雅黑", 12);
            password.BackColor = Color.White;
            password.ForeColor = Color.Black;
            password.BorderStyle = BorderStyle.FixedSingle;
            password.Padding = new Padding(10);
            password.Location = new Point(80, 150);
            password.Size = new Size(200, 30);
         
            password.Text = PasswordPlaceholder;

            // 设置显示密码复选框样式
            showPasswordCheckbox = new CheckBox();
            showPasswordCheckbox.Text = "显示密码";
            showPasswordCheckbox.Location = new Point(80, 185);

            // 设置登录按钮样式
            button1.Font = new Font("微软雅黑", 10, FontStyle.Bold);
            button1.ForeColor = Color.White;
            button1.BackColor = Color.MediumSeaGreen;
            button1.FlatStyle = FlatStyle.Flat;
            button1.FlatAppearance.BorderSize = 0;
            button1.Padding = new Padding(5);
            button1.Location = new Point(centerX, 220);
            button1.Size = new Size(120, 40);
            button1.TextAlign = ContentAlignment.MiddleCenter;
            button1.MouseEnter += (s, e) => { button1.BackColor = Color.SeaGreen; };
            button1.MouseLeave += (s, e) => { button1.BackColor = Color.MediumSeaGreen; };
        }

        private void SetupEventHandlers()
        {
            // 用户名输入框事件处理
            user.Enter += (s, e) => ClearPlaceholder((TextBox)s, UsernamePlaceholder);
            user.Leave += (s, e) => RestorePlaceholder((TextBox)s, UsernamePlaceholder);

            // 密码输入框事件处理
            password.Enter += (s, e) => ClearPlaceholder((TextBox)s, PasswordPlaceholder);
            password.Leave += (s, e) => RestorePlaceholder((TextBox)s, PasswordPlaceholder);

            // 显示密码复选框事件处理
            showPasswordCheckbox.CheckedChanged += (s, e) =>
            {
                if (password.Text != PasswordPlaceholder)
                {
                    password.PasswordChar = showPasswordCheckbox.Checked ? '\0' : '*';
                }
            };

            // 登录按钮点击事件处理
            button1.Click += (s, e) =>
            {
                // The open-source build does not embed credentials in source code.
                // This legacy form is not used by Program.Main; keep the button harmless
                // if a developer opens the form manually in Visual Studio.
                this.DialogResult = DialogResult.OK;
                this.Close();
            };
        }

        private void ClearPlaceholder(TextBox textBox, string placeholder)
        {
            if (textBox.Text == placeholder)
            {
                textBox.Text = "";
                if (textBox.Name.Contains("password"))
                {
                    textBox.PasswordChar = '*';
                }
            }
        }

        private void RestorePlaceholder(TextBox textBox, string placeholder)
        {
            if (string.IsNullOrEmpty(textBox.Text))
            {
                textBox.Text = placeholder;
                if (textBox.Name.Contains("password"))
                {
                    textBox.PasswordChar = '\0';
                }
            }
        }
    }
}
