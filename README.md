PMD plugin for ReviewBot
========================

reviewbot-pmd is a plugin for [ReviewBot](https://github.com/reviewboard/ReviewBot) to automatically run PMD on code submitted to a [Review Board](https://www.reviewboard.org/) instance.

[PMD](http://pmd.sourceforge.net/) is a static code analysis tool to detect common programming flaws. It supports Java, Javascript, XML and XSL. It is highly customizable: each code violation is defined by a rule, and one can easily select which rule to apply or exclude. It is also possible to write custom rules, using either an XPath syntax or pure Java code.

Installation
============

This plugin requires an up-and-running ReviewBoard instance, with the ReviewBot extension enabled and the ReviewBot worker running. See the [ReviewBot installation instructions](https://github.com/reviewboard/ReviewBot#installation) for more information.

You will also need PMD. You can download and install the latest version from [the PMD homepage](http://pmd.sourceforge.net/). Download the archive and extract it somewhere convenient, e.g. '/opt/pmd/'.

To install the plugin, run the following commands:

```bash
git clone git://github.com/jjst/reviewbot-pmd.git
cd reviewbot-pmd
python setup.py install
```

Now that the tool has been installed, it must be registered with the Review Bot extension. To do so, follow these instructions:

1.  Go to the extension list in the Review Board admin panel.
2.  Click the **Database** button for the Review Bot extension.
3.  Click the **Review bot tools** link.
4.  Click **Refresh installed tools** in the upper right of the page.

The **PMD Source Code Analyzer** tool should now be listed in the Review Bot available tools list.

Configuration
=============

You can access reviewbot-pmd's configuration options by clicking on the tool name under the **Review bot tools** page. In addition to the standard configuration options, reviewbot-pmd requires the following mandatory settings to be configured:

* **PMD installation path**: this is the path where you extracted PMD.
* **PMD rulesets**: the comma-separated list of rulesets to use to detect violations. A ruleset is a set of related PMD rules (you can find a list of available rulesets and rules [here](http://pmd.sourceforge.net/pmd-5.1.1/rules/index.html)). A ruleset can be referenced by either its name, its relative path inside the Java classpath, or its full path. The simplest way to use a [custom ruleset](http://pmd.sourceforge.net/pmd-5.1.1/howtomakearuleset.html) is probably to reference it by its full path.

The following optional settings are also available:

* **Enable Markdown**: if enabled then PMD will post its comments using [rich text](https://www.reviewboard.org/docs/manual/2.0/users/markdown/). Note that this is an experimental feature that needs a [custom version of ReviewBot](https://github.com/jjst/ReviewBot/tree/markdown-support) with Markdown support.
* **Minimum serverity for open issues**: if **Open issues** is enabled then this is the minimum severity (also called priority) a rule must have for reviewbot-pmd to open an issue if it finds a violation of that rule. By default reviewbot-pmd will only open an issue for violations of the highest severity level.




