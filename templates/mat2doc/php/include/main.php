<?php
/* ****************************************************************** **
 * Function printpage($title,$keywords,$seealso,$demos,$content,$doctype)
 * 		print the page composed of 
 * 			- header
 * 			- footer
 * 			- main menu
 * 			- content
 * 			- submenu
 * Edit this function to create your template
 * 
 * Author: Nathanael Perraudin
 * Date:   18.03.2013
 * ****************************************************************** */
function printpage($title,$keywords,$seealso,$demos,$content,$doctype)
{
// define general variable
global $path_include;

// include functions file
include($path_include."functions.php");

// include header
include($path_include."header.php");
print_header($title,$keywords);

//Start of the page
include($path_include."topofpage.php");


// -- print the page --
echo'<div id="main_content">'; 
	
	// -- create a first table with 20% for the menu and 80% for the rest
	echo '<table width="100%">
	<tr><td valign="top" width="20%">';

	//	1) main menu
	include("mainmenu.php");
	echo '</td><td valign="top"  width="80%">';// change of cell in the tabular
	
		echo '<table width=100% ><tr valign=top><td>'; //create a second table

		//	2) main content
		echo '<div id="content">';
		echo $content;
		echo '</div>';
		echo'</td><td>'; // change of cell in the tabular

		// 	3) right menu
		// this function is discribed in functions.php
		printsubmenu($seealso,$demos,$doctype);

		echo'</tr></td></table>'; //close the table


	echo '</td>
	</tr>
	</table>';//close the second table
	
echo '</div>'; 


// print some footer information
include($path_include."bottomofpage.php");

//close the page
include($path_include."footer.php");
}


?>


