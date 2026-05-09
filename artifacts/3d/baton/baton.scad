
// --- MASTER CONFIGURATION ---
wall_t = 2.9;       
lid_clearance = 0.5; 
lid_wall = 2.0;
lid_depth = wall_t*1.5;


margin = 2.9;
pi_hole_h = 58;
pi_hole_w = 23;


dweii_x = margin;
dweii_hole_h = 37;
dweii_hole_w = 83;

dweii_z=12;
pi_z = dweii_z + 27;
vault_z = pi_z+15-wall_t;

usbc_w = 13;
usbc_h = 8;



plate_w = dweii_x+dweii_hole_w+margin;
plate_h = margin*2 + pi_hole_h    ;
     




pi_port_y=margin+wall_t;



lid_x=wall_t+pi_hole_w+8;

bayite_hole_w = 23;
bayite_hole_h = 14.5;
bayite_display_h = 7;

ext_r = 6; // 4mm radius gives a nice 'rugged' curve

// --- 1. THE MAIN BOX ---
difference() {
    
    // POSITIVE SPACE (Main Chassis + Integrated Wings)
    union() {
        // --- THE MAIN ROUNDED BOX ---
        hull() {
            translate([ext_r, ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([plate_w + (wall_t*2) - ext_r, ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([ext_r, plate_h + (wall_t*2) - ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
        }

       // --- THE NO-SEW TRIGLIDE STRAP WINGS (LONG-SIDE ROTATION) ---
        wing_w = 60;      // Now follows the width of the box
        wing_h = 16;      // Depth of the wing extension
        wing_z = 6.0;      // Thickened to 6mm for high-tension durability
        slot_h = 3.5;      // Width of the elastic path
        bar_h  = 4.0;      // The central friction bar
        
        for(side = [0, 1]) { 
            // side 0 = Top Wall, side 1 = Bottom Wall
            translate([(plate_w + wall_t*2)/2 - wing_w/2, side * (plate_h + wall_t*2), 0])
            difference() {
                // The Wing Body
                hull() {
                    // Fusion points to the main wall
                    translate([2, side == 0 ? 0 : -2, 0]) cube([wing_w-4, 2, wing_z + 2]); 
                    // Outer rounded edges
                    translate([4, side == 0 ? -wing_h + 4 : wing_h - 4, 0]) cylinder(r=4, h=wing_z, $fn=30);
                    translate([wing_w - 4, side == 0 ? -wing_h + 4 : wing_h - 4, 0]) cylinder(r=4, h=wing_z, $fn=30);
                }
                
                // SLOT 1 (Inner - closest to chassis)
                translate([(wing_w - 52)/2, side == 0 ? -slot_h - bar_h - 3.5 : 3.5 + bar_h, -1]) 
                    cube([52, slot_h, wing_z + 10]);

                // SLOT 2 (Outer - the ladder lock)
                translate([(wing_w - 52)/2, side == 0 ? -slot_h - 2.5 : 2.5, -1]) 
                    cube([52, slot_h, wing_z + 10]);
            }
        }
    }
    


    // NEGATIVE SPACE (The Drills)
    
    

    // Hollow out center
    translate([wall_t, wall_t, wall_t]) {
        hull() {
            // Internal Top-Left
            translate([ext_r-wall_t, ext_r-wall_t, 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Top-Right
            translate([plate_w - (ext_r-wall_t), ext_r-wall_t, 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Bottom-Left
            translate([ext_r-wall_t, plate_h - (ext_r-wall_t), 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Bottom-Right
            translate([plate_w - (ext_r-wall_t), plate_h - (ext_r-wall_t), 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
        }
    }
    
    /*
    // pi sides
    translate([wall_t+margin, -1, pi_z+ wall_t-1]) // Move start slightly outside the x=0 plane
    cube([lid_x-(wall_t+margin), plate_h + wall_t*2+2, vault_z - pi_z + 4]);

    // pi front
    translate([-1, wall_t+margin, wall_t+pi_z-usbc_h/2+1+3/2]) // Move start slightly outside the x=0 plane
    cube([16, pi_hole_h, 20]);
    */

    // pi
    translate([-1, -1, pi_z+ wall_t-2]) // Move start slightly outside the x=0 plane
    cube([lid_x+1, plate_h + wall_t*2+2, vault_z - pi_z + 4]);

    // dweii port
    translate([-1, (plate_h+wall_t*2)/2 - usbc_w/2, wall_t+dweii_z-usbc_h/2-1-3/2])
    cube([16, usbc_w, usbc_h]);
    
    // button
    button_d = 12.5;
    translate([plate_w-button_d/2- 5, -1, (wall_t*2+vault_z)/2]) 
    rotate([-90, 0, 0]) cylinder(h=20, d=button_d, $fn=50);
   
    

}

// --- UNIVERSAL REINFORCED RECTANGULAR STANDOFF ---
module standoff(x, y, h=23) {
    translate([x, y, 0]) 
    difference() {
       
        // The Core: Now a square block for universal wall-fusion
        // Center it so the screw hole stays at (x,y)
        translate([-3, -3, 0]) 
            cube([6, 6, h]); 
            
           
        // The Screw Hole (Circular is better for threads)
        translate([0,0,0]) 
            cylinder(h=h+2, d=1.8, $fn=50); 
    }
}
// --- STANDOFFS (Now inside the union and translated correctly) ---
translate([wall_t, wall_t, wall_t]) {
    
    //pi
    
    standoff(margin, (plate_h - pi_hole_h)/2, pi_z);
    difference(){
        standoff(margin, (plate_h - pi_hole_h)/2 + pi_hole_h, pi_z);  
        translate([-1,(plate_h - pi_hole_h)/2 + pi_hole_h-5, pi_z-2])
        cube([2.5,110,10]);
    }
    
    standoff(margin+pi_hole_w, (plate_h - pi_hole_h)/2, pi_z);  
    standoff(margin+pi_hole_w, (plate_h - pi_hole_h)/2 + pi_hole_h, pi_z); 
    
    //dweii
    standoff(dweii_x, (plate_h - dweii_hole_h)/2, dweii_z); 
    standoff(dweii_x, (plate_h - dweii_hole_h)/2 + dweii_hole_h, dweii_z); 
    standoff(dweii_x+dweii_hole_w, (plate_h - dweii_hole_h)/2, dweii_z);  
    standoff(dweii_x+dweii_hole_w, (plate_h - dweii_hole_h)/2 + dweii_hole_h, dweii_z); 
    
    //lid
    standoff(lid_x + margin-wall_t, margin, vault_z-(lid_depth - wall_t));
    standoff(lid_x + margin-wall_t, plate_h-margin, vault_z-(lid_depth - wall_t));
    standoff(plate_w-margin, margin, vault_z-(lid_depth - wall_t));
    standoff(plate_w-margin, plate_h-margin, vault_z-(lid_depth - wall_t));
   
}
        

// --- 2. THE LID ---
translate([0, plate_h + 40, 0]) 



difference() {
    
    // POSITIVE SPACE (Rounded Right Side, Sharp Left Side)
    union(){
         hull() {
            // Left-Top (Sharp corner at lid_x)
            translate([lid_x, 0, 0]) 
                cylinder(r=0.1, h=lid_depth, $fn=4);
            
            // Left-Bottom (Sharp corner at lid_x)
            translate([lid_x, plate_h + (wall_t*2), 0]) 
                cylinder(r=0.1, h=lid_depth, $fn=4);
                
            // Right-Top (Rounded to match box)
            translate([plate_w + (wall_t*2) - ext_r, ext_r, 0]) 
                cylinder(r=ext_r, h=lid_depth, $fn=50);
                
            // Right-Bottom (Rounded to match box)
            translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, 0]) 
                cylinder(r=ext_r, h=lid_depth, $fn=50);
        }


        translate([lid_x + (plate_w-lid_x)/2 - 38/2, wall_t+plate_h/2 - 38/2, lid_depth])
        cube([38, 38,  (lid_depth-0.8)]);



    }
   

    //lip - negative version of box, but enlarged a little for clearance
    difference(){
        //remove material
        hull() {
            // Top-Left
            translate([ext_r, ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Top-Right
            translate([plate_w + (wall_t*2) - ext_r, ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Bottom-Left
            translate([ext_r, plate_h + (wall_t*2) - ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Bottom-Right
            translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
        }


        // excluded from removal to create the lip
        translate([wall_t, wall_t, 0]) {
            hull() {
                // Internal Top-Left
                translate([ext_r-wall_t-lid_clearance, ext_r-wall_t-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Top-Right
                translate([plate_w - (ext_r-wall_t)-lid_clearance, ext_r-wall_t-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Bottom-Left
                translate([ext_r-wall_t-lid_clearance, plate_h - (ext_r-wall_t)-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Bottom-Right
                translate([plate_w - (ext_r-wall_t)-lid_clearance, plate_h - (ext_r-wall_t)-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            }
        }


    }
 

    
    // holes
    translate([lid_x + margin, margin+wall_t,-1])
    cylinder(h=lid_depth+10, d=2.2, $fn=50); 
    
    translate([lid_x + margin, plate_h+wall_t-margin,-1])
    cylinder(h=lid_depth+10, d=2.2, $fn=50); 
    
    translate([wall_t+plate_w-margin, margin+wall_t,-1])
    cylinder(h=lid_depth+10, d=2.2, $fn=50); 
    
    translate([wall_t+plate_w-margin, plate_h+wall_t-margin,-1])
    cylinder(h=lid_depth+10, d=2.2, $fn=50); 
    

    // bayite hole
    translate([lid_x + (plate_w-lid_x)/2 - bayite_hole_h/2, wall_t+plate_h/2 - bayite_hole_w/2, 0.8])
    cube([bayite_hole_h, bayite_hole_w, lid_depth+10]);
   
  
}




